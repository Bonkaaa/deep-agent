import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.components.mcp_client import create_mcp_client

async def main():
    client = await create_mcp_client()
    # Call get_tools to initialize the session/connections
    await client.get_tools()
    print("All attributes including private:")
    for k in dir(client):
        val = getattr(client, k)
        print(f"- {k}: {type(val)}")

if __name__ == "__main__":
    asyncio.run(main())
