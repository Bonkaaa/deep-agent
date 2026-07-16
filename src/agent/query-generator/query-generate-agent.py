from pathlib import Path
import json
import sys
from ...utils import setup_logger
from ...config import ROOT_DIR

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend, FilesystemBackend
from langgraph.store.memory import InMemoryStore, logger
from langchain_mcp_adapters.client import MultiServerMCPClient

try:
    from ...components.get_llm import get_llm
    from ...components.template import QUERY_GENERATE_SYSTEM_PROMPT
    from ...components.mcp_client import create_mcp_client
    from ...components.structured_output import VulnerabilityType
    from ...utils import collect_tool_calls
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import QUERY_GENERATE_SYSTEM_PROMPT
    from src.components.structured_output import VulnerabilityType
    from src.utils import collect_tool_calls


class QueryGenerateAgent:
    def __init__(self):
        self.llm = get_llm()
        self.system_prompt = QUERY_GENERATE_SYSTEM_PROMPT
        self.store = InMemoryStore()

    async def create_agent(self):

        mcp_client = await create_mcp_client()

        mcp_tools = mcp_client.get_tools()

        return create_deep_agent(
            name="QueryGenerateAgent",
            system_prompt=self.system_prompt,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes={
                    "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
                    "/vic/": FilesystemBackend(root_dir=ROOT_DIR / "data" / self.data_name, virtual_mode=True),
                    "/skills/": FilesystemBackend(root_dir=ROOT_DIR / "skills" / "query-generate", virtual_mode=True),
                },
            ),
            store=self.store,
            tools=mcp_tools,
        )
    
    async def run(self, data_name: str):
        self.data_name = data_name
        self.agent = await self.create_agent()
        logger.info(f"QueryGenerateAgent created for data_name: {data_name}")
        
        try:
            result = await self.agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""
                                Based on all the tools and information available, please generate a CodeQL query to expose the vulnerability.
                            """
                        }
                    ]
                }
            )
            logger.info(f"Query generation result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error during query generation: {e}")
            raise
    

    