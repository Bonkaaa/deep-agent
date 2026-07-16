from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

CODEQL_CLI_PATH = os.getenv("CODEQL_CLI_PATH")
ROOT_DIR = os.getenv("ROOT_DIR")

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
                "args": ["codeql-development-mcp-server/server/dist/codeql-development-mcp-server.js"],
                "env": {
                    "CODEQL_CLI_PATH": CODEQL_CLI_PATH,
                    "WORKSPACE_ROOT": ROOT_DIR,
                }

            }
        }
    )