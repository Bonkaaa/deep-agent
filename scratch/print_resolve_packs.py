import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.components.mcp_client import create_mcp_client

async def main():
    mcp_client = await create_mcp_client()
    mcp_tools = await mcp_client.get_tools()
    for tool in mcp_tools:
        if tool.name == "codeql_resolve_packs":
            print(f"Tool: {tool.name}")
            print(f"Args Schema: {getattr(tool, 'args_schema', None)}")
            print(f"Args: {getattr(tool, 'args', None)}")

if __name__ == "__main__":
    asyncio.run(main())
