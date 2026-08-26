import json
import time
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from dotenv import load_dotenv
from ..config import ROOT_DIR, CODEQL_CLI_PATH
from pathlib import Path

load_dotenv()  # Load environment variables from .env file

CODEQL_CLI_PATH = str(CODEQL_CLI_PATH)
ROOT_DIR_STR = str(Path(ROOT_DIR))  # Ensure ROOT_DIR is a string for environment variable usage

async def create_mcp_client() -> MultiServerMCPClient:
    """
    Create a MultiServerMCPClient instance.

    Returns:
        MultiServerMCPClient: An instance of MultiServerMCPClient.
    """
    return MultiServerMCPClient(
        {
            "codeql": {
                "transport": "stdio",
                "command": "node",
                "args": ["mcp_server_wrapper.js"],
                "env": {
                    "CODEQL_CLI_PATH": CODEQL_CLI_PATH,
                    "WORKSPACE_ROOT": ROOT_DIR_STR,
                }
            }
        }
    )

if __name__ == "__main__":
    import asyncio

    async def main():
        mcp_client = await create_mcp_client()
        # time.sleep(10)  # Wait for the server to start
        mcp_tools = await mcp_client.get_tools()

        mcp_tools_dict = []

        # Convert to JSON serializable format
        for tool in mcp_tools:
            tool_name = tool.name
            tool_description = tool.description
            tool_parameters = tool.args_schema
            tool_response_format = tool.response_format

            mcp_tools_dict.append({
                "name": tool_name,
                "description": tool_description,
                "parameters": tool_parameters,
                "response_format": tool_response_format
            })

        # save the tools to a JSON file
        tools_file_path = ROOT_DIR / "mcp_tools.json"
        with open(tools_file_path, "w") as f:
            json.dump(mcp_tools_dict, f, indent=4)
        

    asyncio.run(main())