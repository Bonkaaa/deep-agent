from deepagents import create_deep_agent
from deepagents.backend import StoreBackend, CompositeBackend, StateBackend
from deepagents.backend.utils import create_file_data
from langgraph.store.memory import InMemoryState
from langchain.tools import tool, ToolRuntime

from dataclasses import dataclass
from pathlib import Path
import os



store = InMemoryState()

skill_path = Path("/app/skills/taint_path_tracking")
if skill_path.exists():
    store.put(
        namespace=("filesystem",),
        key="./skills/taint_path_tracking/SKILL.md",
        data=create_file_data(skill_path.read_text(encoding="utf-8")),
    )

composite_backend = lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={
        "/memories/": StoreBackend(rt),
    }
)

@dataclass
class Context:
    folder_path: str 

    @classmethod
    def from_dict(cls, data: dict) -> "Context":
        return cls(folder_path=data["folder_path"])
    

@tool(parse_docstring=True)
def fetch_folder_path(runtime: ToolRuntime[Context]):
    """Fetch the folder path for taint path tracking.

    Args:
        runtime (ToolRuntime[Context]): The runtime context containing the folder path.
    """
    return runtime.context.folder_path

@tool
def insert_comment_at_line(file_path: str, line_number: int, comment: str):
    """Insert a comment at a specific line in a file.
    
    Use this to add comments to the code to explain the taint path or any relevant information.
    Example comment: // taint: <previous_tainted_variable>
    """
    if not os.exists(file_path):
        return f"Error: File {file_path} does not exist."
    
    try:
        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Validate line number
        if line_number < 1 or line_number > len(lines):
            return f"Error: Line number {line_number} is out of range for file {file_path} which has {len(lines)} lines."
        
        # Adjust line number for 0-based index
        target_line = line_number - 1

        # Preprocess the line to ensure we don't lose any existing content
        original_line = lines[target_line].rstrip("\n").rstrip("\r")

        # Ensure no space in the comment
        if not comment.startswith(" ") or not comment.startswith("\t"):
            comment = " " + comment

        # Insert comment at the end of the line
        lines[target_line] = original_line + comment + "\n"

        # Write back to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return f"Comment inserted successfully at line {line_number} in file {file_path}."
    
    except Exception as e:
        return f"Error inserting comment: {str(e)}"

    

@tool
def extract_code_snippets(file_path: str, start_line: int, end_line: int):
    """Extract code snippets from a file given a line range.
    
    Use this to extract relevant code snippets that are part of the taint path for analysis or explanation.
    """
    if not os.path.exists(file_path):
        return f"Error: File {file_path} does not exist."
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return f"Error: Invalid line range. File {file_path} has {len(lines)} lines."

        # Extract the specified lines
        code_snippet = "".join(lines[start_line - 1:end_line])
        return code_snippet
    
    except Exception as e:
        return f"Error extracting code snippet: {str(e)}"

agent = create_deep_agent(
    name="TaintPathTrackingAgent",
    model=llm,
    backend=composite_backend,
    tools=[fetch_folder_path, insert_comment_at_line, extract_code_snippets],
    store=store,
    skills=["./skills/taint_path_tracking/SKILL.md"],
    context_schema=Context,
)

