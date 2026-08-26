import sys
from pathlib import Path

from src import artifacts
from src.agent.base import BaseVICAgent

try:
    from ..components.template import SOURCE_SINK_SYSTEM_PROMPT
    from ..components.structured_output import SourceSinkAnalysis
except ImportError:
    from src.components.template import SOURCE_SINK_SYSTEM_PROMPT
    from src.components.structured_output import SourceSinkAnalysis


class SourceSinkAgent(BaseVICAgent):
    stage = artifacts.SOURCE_SINK
    agent_name = "SourceSinkIdentificationAgent"
    system_prompt = SOURCE_SINK_SYSTEM_PROMPT
    response_format = SourceSinkAnalysis

    def __init__(self, data_name: str):
        super().__init__(vic=data_name)

    def task_message(self, vuln_type: str, *args, **kwargs) -> str:
        return f"""
            Vulnerability Type: {vuln_type}

            Please analyze the provided pre-VIC folder, post-VIC folder, and diff files in the folder /vic to identify the top 5 most suspicious source-sink pairs related to taint flows.

            Focus on changes introduced by the vulnerability-inducing commit and document your findings according to the instructions in the SKILL.md.

            Remember to read the diff first, then the exact touched files, and then only the directly connected local helpers or imports that are needed to explain a flow.
            You can find the SKILL.md in the /skills directory for detailed instructions on how to structure your analysis and findings.
        """


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/agent/source-sink-agent.py <data_name> <vuln_type>")
        sys.exit(1)

    vic_name = sys.argv[1]
    vuln_type = sys.argv[2]

    agent = SourceSinkAgent(vic_name)
    result = agent.run(vuln_type)
    
    # Extract structural payload for backwards compatibility in console output
    payload = result.get('structured_response') or result.get('structured_output')
    print(f"Final Result: {payload}")