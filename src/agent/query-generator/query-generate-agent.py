import asyncio
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from src import artifacts
from src.agent.base import AsyncVICAgent

try:
    from ...components.template import QUERY_GENERATE_SYSTEM_PROMPT
    from ...components.mcp_client import create_mcp_client
    from ...components.structured_output import QueryGeneration
    from ...config import ALLOWED_MCP_TOOLS_QUERY_GENERATE
except ImportError:
    from src.components.template import QUERY_GENERATE_SYSTEM_PROMPT
    from src.components.mcp_client import create_mcp_client
    from src.components.structured_output import QueryGeneration
    from src.config import ALLOWED_MCP_TOOLS_QUERY_GENERATE



import langchain_mcp_adapters.tools as lmt
_orig_convert = lmt.convert_mcp_tool_to_langchain_tool

def patched_convert(session, tool, **kwargs):
    mapping = {}
    if hasattr(tool, 'inputSchema') and tool.inputSchema and 'properties' in tool.inputSchema:
        properties = tool.inputSchema['properties']
        new_properties = {}
        for k, v in properties.items():
            if '-' in k:
                new_k = k.replace('-', '_')
                new_properties[new_k] = v
                mapping[new_k] = k
            else:
                new_properties[k] = v
        tool.inputSchema['properties'] = new_properties
        
        if 'required' in tool.inputSchema:
            required = tool.inputSchema['required']
            new_required = []
            for r in required:
                if '-' in r:
                    new_required.append(r.replace('-', '_'))
                else:
                    new_required.append(r)
            tool.inputSchema['required'] = new_required

    lc_tool = _orig_convert(session, tool, **kwargs)
    original_coro = lc_tool.coroutine

    async def wrapped_call(*args, **call_kwargs):
        new_kwargs = {}
        for k, v in call_kwargs.items():
            if k in mapping:
                new_kwargs[mapping[k]] = v
            else:
                new_kwargs[k] = v
        return await original_coro(*args, **new_kwargs)

    lc_tool.coroutine = wrapped_call
    return lc_tool

lmt.convert_mcp_tool_to_langchain_tool = patched_convert


class QueryGenerateAgent(AsyncVICAgent):
    stage = artifacts.QUERY_GENERATE
    agent_name = "QueryGenerateAgent"
    system_prompt = QUERY_GENERATE_SYSTEM_PROMPT
    response_format = QueryGeneration

    async def tools_async(self) -> list[Any] | None:
        mcp_client = await create_mcp_client()
        mcp_tools = await mcp_client.get_tools()
        scoped_mcp_tools = [tool for tool in mcp_tools if tool.name in ALLOWED_MCP_TOOLS_QUERY_GENERATE]
        
        # Rewriter for /vic/ paths to real paths on execution
        from src.config import ROOT_DIR
        
        def rewrite_path(val: Any) -> Any:
            if isinstance(val, str):
                if val.startswith("/vic/"):
                    suffix = val[len("/vic/"):]
                    return str((Path(ROOT_DIR) / "data" / self.vic / suffix).resolve())
                elif val.startswith("/skills/"):
                    suffix = val[len("/skills/"):]
                    return str((Path(ROOT_DIR) / "skills" / "query-generate" / suffix).resolve())
            return val

        wrapped_tools = []
        for tool in scoped_mcp_tools:
            original_coroutine = tool.coroutine
            
            async def wrapped_coroutine(*args, _orig_coro=original_coroutine, **kwargs):
                new_kwargs = {k: rewrite_path(v) for k, v in kwargs.items()}
                new_args = tuple(rewrite_path(a) for a in args)
                return await _orig_coro(*new_args, **new_kwargs)
            
            tool.coroutine = wrapped_coroutine
            wrapped_tools.append(tool)

        return wrapped_tools

    def task_message(self, *args, **kwargs) -> str:
        feedback = kwargs.get("feedback")
        if feedback:
            return f"Feedback from previous evaluation:\n{feedback}\nPlease fix or refine the CodeQL query according to this feedback."
        else:
            return "Based on all the tools and information available, please generate a CodeQL query to expose the vulnerability."

    def _persist(self, result: Any, structured: BaseModel):
        super()._persist(result, structured)
        if hasattr(structured, "query_content") and structured.query_content:
            artifacts.write_text(self.vic, self.stage, "query", structured.query_content, self.iteration)


async def main():
    agent = QueryGenerateAgent()
    # For execution verification without instantiation of the deep agent backend
    mcp_tools = await agent.tools_async()
    print("MCP Tools available for QueryGenerateAgent:")
    if mcp_tools:
        for tool in mcp_tools:
            print(f"- {tool.name}: {tool.description}")
    else:
        print("No tools found or allowed.")


if __name__ == "__main__":
    asyncio.run(main())