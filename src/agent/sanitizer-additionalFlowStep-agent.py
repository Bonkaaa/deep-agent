import sys
from pathlib import Path

from src import artifacts
from src.agent.base import BaseVICAgent
from deepagents.backends import FilesystemBackend

try:
    from ..components.template import SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT
    from ..components.structured_output import FlowModelingAnalysis
    from ..config import ROOT_DIR
except ImportError:
    from src.components.template import SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT
    from src.components.structured_output import FlowModelingAnalysis
    from src.config import ROOT_DIR


class SanitizerAdditionalFlowStepAgent(BaseVICAgent):
    stage = artifacts.SANITIZER_FLOW_STEP
    agent_name = "SanitizerAdditionalFlowStepAgent"
    system_prompt = SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT
    response_format = FlowModelingAnalysis
    skill_name = "sanitizer-additionalFlowStep"

    def __init__(self, data_name: str):
        super().__init__(vic=data_name)

    def extra_routes(self) -> dict[str, FilesystemBackend]:
        return {
            "/source-sink-agent_output/": FilesystemBackend(
                root_dir=Path(ROOT_DIR) / "data" / self.vic / "source-sink-agent_output",
                virtual_mode=True
            )
        }

    def task_message(self, vuln_type: str, *args, **kwargs) -> str:
        return f"""
            Vulnerability type: {vuln_type}
            Based on the source-sink analysis results, identify any additional flow steps and sanitizers that may be present in the code. 
            
            First, immediately read the source-sink analysis results in `/source-sink-agent_output/source_sink_analysis.txt` and check the touched files in `/vic/diff.diff` and `/vic/after/src/index.js` (or other files touched).
            Do not perform multiple unnecessary directory listings or search files. Read these relevant files immediately, analyze the flow and sanitizers, document your notes in `/memories/flow_modeling_notes.md`, and then immediately output the final structured response using the response format tool. Ensure that the output is structured according to the FlowModelingAnalysis model.
        """


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/agent/sanitizer-additionalFlowStep-agent.py <data_name> <vuln_type>")
        sys.exit(1)

    data_name = sys.argv[1]
    vuln_type = sys.argv[2]

    agent = SanitizerAdditionalFlowStepAgent(data_name)
    result = agent.run(vuln_type)
    
    # Extract structural payload for backwards compatibility in console output
    payload = result.get('structured_response') or result.get('structured_output')
    print(f"Final Result: {payload}")