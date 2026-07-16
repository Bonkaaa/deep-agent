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
    from ..components.template import SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT
    from ..components.structured_output import FlowModelingAnalysis
    from ..utils import collect_tool_calls
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT
    from src.components.structured_output import FlowModelingAnalysis
    from src.utils import collect_tool_calls

ROOT_DIR = Path(ROOT_DIR)

logger = setup_logger("sanitizer-additionalFlowStep-agent.log", "SanitizerAdditionalFlowStepAgentLogger")

class SanitizerAdditionalFlowStepAgent:
    def __init__(self, data_name: str):
        self.data_name = data_name
        self.llm = get_llm()
        self.store = InMemoryStore()
        self.agent = self.create_agent()

    def create_agent(self):
        return create_deep_agent(
            name="SanitizerAdditionalFlowStepAgent",
            system_prompt=SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes={
                    "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
                    "/vic/": FilesystemBackend(root_dir=ROOT_DIR / "data" / self.data_name, virtual_mode=True),
                    "/skills/": FilesystemBackend(root_dir=ROOT_DIR / "skills" / "sanitizer-additionalFlowStep", virtual_mode=True),
                    "/source-sink-agent_output/": FilesystemBackend(root_dir=ROOT_DIR / "data" / self.data_name / "source-sink-agent_output", virtual_mode=True),
                },
            ),
            store=self.store,
            response_format=FlowModelingAnalysis,
        )
    def run(self, vuln_type: str):
        logger.info(f"SanitizerAdditionalFlowStepAgent created for data_name: {self.data_name}")
        
        try:
            result = self.agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""
                                Vulnerability type: {vuln_type}
                                Based on the source-sink analysis results, identify any additional flow steps and sanitizers that may be present in the code. Provide a detailed analysis of the flow steps and sanitizers, including their types, descriptions, code hints, and confidence levels. Ensure that the output is structured according to the FlowModelingAnalysis model.
                            """,
                        }
                    ]
                },
                config=
                    {
                        "configurable": {
                            "thread_id": "34567", 
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
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save the result to a txt file
        output_file = output_dir / "sanitizer-additionalFlowStep-agent-output" / f"{self.data_name}_sanitizer_additionalFlowStep_results.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            f.write(str(result['structured_output'] if 'structured_output' in result else result))

        # Save tool calls to a separate file for review
        tool_calls_path = output_dir / "tool-calls" / f"{self.data_name}_sanitizer_additionalFlowStep_tool_calls.json"
        tool_calls = collect_tool_calls(result)
        with open(tool_calls_path, "w") as f:
            f.write(json.dumps(tool_calls, indent=2, ensure_ascii=False, default=str))
        
        return result
    
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/agent/sanitizer-additionalFlowStep-agent.py <data_name> <vuln_type>")
        sys.exit(1)

    data_name = sys.argv[1]
    vuln_type = sys.argv[2]

    agent = SanitizerAdditionalFlowStepAgent(data_name)
    logger.info(f"Running SanitizerAdditionalFlowStepAgent for data_name: {data_name} and vuln_type: {vuln_type}")

    result = agent.run(vuln_type)

    if result:
        logger.info(f"SanitizerAdditionalFlowStepAgent completed successfully. Result: {result['structured_output'] if 'structured_output' in result else result}")