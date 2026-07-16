from pathlib import Path
import json
import os
import sys
from ..utils import collect_tool_calls, setup_logger
from ..config import ROOT_DIR

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend, FilesystemBackend
from langgraph.store.memory import InMemoryStore


try:
    from ..components.get_llm import get_llm
    from ..components.template import SOURCE_SINK_SYSTEM_PROMPT
    from ..components.structured_output import SourceSinkAnalysis
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import SOURCE_SINK_SYSTEM_PROMPT
    from src.components.structured_output import SourceSinkAnalysis

ROOT_DIR = Path(ROOT_DIR)

logger = setup_logger("source-sink-agent.log", "SourceSinkAgentLogger")

class SourceSinkAgent:
    def __init__(self, data_name: str):
        self.data_name = data_name
        self.llm = get_llm()
        self.store = InMemoryStore()
        self.agent = self.create_agent()

    def create_agent(self):
        return create_deep_agent(
            name="SourceSinkIdentificationAgent",
            system_prompt=SOURCE_SINK_SYSTEM_PROMPT,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes={
                    "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
                    "/vic/": FilesystemBackend(root_dir=ROOT_DIR / "data" / self.data_name, virtual_mode=True),
                    "/skills/": FilesystemBackend(root_dir=ROOT_DIR / "skills" / "source-sink", virtual_mode=True),
                },
            ),
            store=self.store,
            response_format=SourceSinkAnalysis,
        )

    def run(self, vuln_type: str):
        logger.info(f"SourceSinkAgent created for data_name: {self.data_name}")
        
        try: 
            result = self.agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""
                                Vulnerability Type: {vuln_type}

                                Please analyze the provided pre-VIC folder, post-VIC folder, and diff files in the folder /vic to identify the top 5 most suspicious source-sink pairs related to taint flows.

                                Focus on changes introduced by the vulnerability-inducing commit and document your findings according to the instructions in the SKILL.md.

                                Remember to read the diff first, then the exact touched files, and then only the directly connected local helpers or imports that are needed to explain a flow.
                                You can find the SKILL.md in the /skills directory for detailed instructions on how to structure your analysis and findings.
                            """,
                        }
                    ]
                },
                config=
                    {
                        "configurable": {
                            "thread_id": "12345", 
                            "recursion_limit": 50,
                            "max_steps": 50,
                        }
                    }
            )

            logger.info(f"Successfully invoked the agent. Result: {result}")
        except Exception as e:
            logger.error(f"Error during agent invocation: {str(e)}")
            return
        
        # Set up output directory
        output_dir = ROOT_DIR / "output" / self.data_name 
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save the result to a txt file
        output_file = output_dir / "source-sink-agent-output" / f"{self.data_name}_source_sink_analysis.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!'))

        # Save tool calls to a separate file for review
        tool_calls_path = output_dir / "tool-calls" / f"{self.data_name}_source_sink_tool_calls.json"
        tool_calls = collect_tool_calls(result)
        with open(tool_calls_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(tool_calls, indent=2, ensure_ascii=False, default=str))

        return result
    
if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.error("Insufficient arguments provided. Please run the script with the VIC name and vulnerability type as arguments, e.g., `python src/agent/source-sink-a.py vic1 SQL Injection`.")
        sys.exit(1)

    vic_name = sys.argv[1]
    vuln_type = sys.argv[2]

    agent = SourceSinkAgent(vic_name)
    logger.info(f"SourceSinkAgent created successfully for VIC: {vic_name}")

    result = agent.run(vuln_type)

    if result:
        logger.info(f"Final Result: {result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!'}")