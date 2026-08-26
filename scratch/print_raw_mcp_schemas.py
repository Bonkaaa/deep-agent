import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.components.mcp_client import create_mcp_client

async def main():
    mcp_client = await create_mcp_client()
    # Call raw list_tools from connection
    response = await mcp_client.connection.send_request(
        mcp_client.connection._connection.types.Request(
            method="tools/list",
            params=None
        )
    )
    for tool in response.tools:
        print(f"Tool: {tool.name}")
        schema = tool.inputSchema
        print(f"  Schema: {schema}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
