# ROOT_DIR = "/app" # Running in Docker, we set ROOT_DIR to /app which is the working directory in the container
from pathlib import Path


ROOT_DIR = Path(__file__).parent.parent.resolve() # Running locally, we set ROOT_DIR to the parent directory of the current file

CODEQL_CLI_PATH='C:\Program Files\codeql'

ALLOWED_MCP_TOOLS_QUERY_GENERATE = [
    "codeql_resolve_language",
    "list_codeql_databases",
    "register_database",
    "codeql_resolve_packs"
    "codeql_pack_ls",
    "codeql_pack_install",
    "codeql_resolve_library-path",
    "search_ql_code",
    "read_database_source",
    "create_codeql_query",
    "validate_codeql_query",
    "codeql_lsp_diagnostics",
    "codeql_lsp_completion",
    "codeql_lsp_definition",
    "codeql_lsp_references",
    "codeql_lsp_document_symbols",
    "codeql_query_compile",
    "codeql_query_format"
]