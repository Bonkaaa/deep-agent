from pathlib import Path
import json
import sys
from ..utils import setup_logger
from ..config import ROOT_DIR

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend, FilesystemBackend
from langgraph.store.memory import InMemoryStore

try:
    from ..components.get_llm import get_llm
    from ..components.template import IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
    from ..components.structured_output import VulnerabilityType
    from ..utils import collect_tool_calls
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
    from src.components.structured_output import VulnerabilityType
    from src.utils import collect_tool_calls

ROOT_DIR = Path(ROOT_DIR)

# Set up logging
logger = setup_logger("deep_agent.log", "DeepAgentLogger")

class IdentifyVulnTypeAgent:
    def __init__(self):
        self.llm = get_llm()
        self.system_prompt = IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
        self.store = InMemoryStore()

    def create_agent(self):
        return create_deep_agent(
            name="IdentifyVulnTypeAgent",
            system_prompt=self.system_prompt,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes={
                    "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
                    "/vic/": FilesystemBackend(root_dir=ROOT_DIR / "data" / self.data_name, virtual_mode=True),
                    "/skills/": FilesystemBackend(root_dir=ROOT_DIR / "skills" / "identify-vuln-type", virtual_mode=True),
                },
            ),
            store=self.store,
            response_format=VulnerabilityType,
            skills=["/skills/identify-vuln-type"],
        )
    def run(self, data_name: str):
        self.data_name = data_name
        self.agent = self.create_agent()
        logger.info(f"IdentifyVulnTypeAgent created for data_name: {data_name}")
        
        try:
            result = self.agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""
                                You will be provided with pre-VIC folder, post-VIC folder, PR data and a diff file between the pre-VIC and post-VIC folder. 
                                Your task is to identify the type of vulnerability present in the provided data. Please provide your analysis in a structured format as defined by the VulnerabilityType schema.
                            """,
                        }
                    ]
                },
                config={
                    "configurable": {
                        "thread_id": "23456",
                        "recursion_limit": 50,
                        "max_steps": 50,
                    }
                }
            )

            logger.info(f"Agent invocation completed. Result: {result}")
        except Exception as e:
            logger.error(f"Error during agent invocation: {str(e)}")
            return 

        # Set up output directory
        output_dir = ROOT_DIR / "output" / self.data_name
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save result to a file for review
        output_file = output_dir / "identify-vuln-type-agent-output" / f"{data_name}_identify_vuln_type_result.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!'))

        # Save tool calls to a separate JSON file
        tool_calls_path = output_dir / "tool-calls" / f"{data_name}_identify_vuln_type_tool_calls.json"
        tool_calls = collect_tool_calls(result)
        with open(tool_calls_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(tool_calls, indent=2, ensure_ascii=False, default=str))
        
        return result


    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/agent/identify-vuln-type-agent.py <data_name>")
        sys.exit(1)

    data_name = sys.argv[1]
    agent = IdentifyVulnTypeAgent()
    result = agent.run(data_name)
    print(f"Final Result: {result['structured_response'] if 'structured_response' in result else 'No structured_response field in result!'}")
