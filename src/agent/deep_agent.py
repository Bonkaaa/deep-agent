from pathlib import Path
import json
import os
import sys
from ..utils import setup_logger
from ..config import ROOT_DIR

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend, FilesystemBackend
from deepagents.backends.utils import create_file_data
from langgraph.store.memory import InMemoryStore
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import studio_client

try:
    from ..components.get_llm import get_llm
    from ..components.template import SYSTEM_PROMPT
    from ..components.structured_output import SourceSinkAnalysis
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import SYSTEM_PROMPT
    from src.components.structured_output import SourceSinkAnalysis

# ROOT_DIR = Path(__file__).resolve().parents[2]

ROOT_DIR = Path(ROOT_DIR)

# Set up logging
logger = setup_logger("deep_agent.log", "DeepAgentLogger")


def collect_tool_calls(result):
    tool_calls = []
    messages = result.get("messages", []) if isinstance(result, dict) else []

    for message in messages:
        message_tool_calls = getattr(message, "tool_calls", None)
        if message_tool_calls is None and isinstance(message, dict):
            message_tool_calls = message.get("tool_calls")

        if message_tool_calls:
            tool_calls.extend(message_tool_calls)

    return tool_calls

def create_agent(data_name: Path):

    llm = get_llm()

    store = InMemoryStore()

    return create_deep_agent(
        name="SourceSinkIdentificationAgent",
        system_prompt=SYSTEM_PROMPT,
        model=llm,
        backend=CompositeBackend(
            default=StateBackend(),
            routes={
                "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
                "/vic/": FilesystemBackend(root_dir=ROOT_DIR / "data" / data_name, virtual_mode=True),
                "/skills/": FilesystemBackend(root_dir=ROOT_DIR / "skills" / "source-sink", virtual_mode=True), 
            }
        ),
        store=store,
        # response_format=SourceSinkAnalysis
    )

if __name__ == "__main__":

    if len(sys.argv) < 2:
        logger.error("No VIC name provided. Please run the script with the VIC name as an argument, e.g., `python src/agent/deep_agent.py vic1`.")
        sys.exit(1)

    vic_name = sys.argv[1] if len(sys.argv) > 1 else "vic"

    agent = create_agent(vic_name)
    logger.info(f"Agent created successfully for VIC: {vic_name}")

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"""
                        Please analyze the provided pre-VIC folder, post-VIC folder, and diff files in the folder /vic to identify the top 5 most suspicious source-sink pairs related to taint flows.

                        Focus on changes introduced by the vulnerability-inducing commit and document your findings according to the instructions in the SKILL.md.

                        Remember to read the diff first, then the exact touched files, and then only the directly connected local helpers or imports that are needed to explain a flow.
                        You can find the SKILL.md in the /skills directory for detailed instructions on how to structure your analysis and findings.
                    """
    
                }
            ]
        },
        config=
            {"configurable": {
                "thread_id": "12345", 
                "recursion_limit": 50,
                "max_steps": 50,
                }
            }
    )

    logger.info(f"Result: {result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!'}")


    output_dir = ROOT_DIR / "output" / vic_name
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save result to a file for review
    output_path = output_dir / f"{vic_name}_source_sink_analysis.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(result['structured_response']))

    tool_calls_path = output_dir / f"{vic_name}_tool_calls.json"
    tool_calls = collect_tool_calls(result)
    with open(tool_calls_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(tool_calls, indent=2, ensure_ascii=False, default=str))
        

    # print("Final Result:")
    # print(result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!')

    # response = agent.invoke({
    #     "messages": "List all the tools you currently have access to, specifically focusing on any tools related to CodeQL. Give me their names and a brief summary of what they do."
    # })

    # print("Agent Response:")
    # print(response)