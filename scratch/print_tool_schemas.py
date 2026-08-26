import asyncio
import sys
from pathlib import Path

# Setup sys.path to find src
sys.path.insert(0, str(Path.cwd()))

from src.components.mcp_client import create_mcp_client
from src.config import ALLOWED_MCP_TOOLS_QUERY_GENERATE

async def main():
    mcp_client = await create_mcp_client()
    mcp_tools = await mcp_client.get_tools()
    scoped_mcp_tools = [tool for tool in mcp_tools if tool.name in ALLOWED_MCP_TOOLS_QUERY_GENERATE]
    for tool in scoped_mcp_tools:
        print(f"Tool: {tool.name}")
        print(f"  Description: {tool.description}")
        print(f"  Args Schema: {getattr(tool, 'args_schema', None)}")
        print(f"  Args: {getattr(tool, 'args', None)}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
