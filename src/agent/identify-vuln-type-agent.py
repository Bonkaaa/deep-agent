import sys
from pathlib import Path

from src import artifacts
from src.agent.base import BaseVICAgent

try:
    from ..components.template import IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
    from ..components.structured_output import VulnerabilityType
except ImportError:
    from src.components.template import IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
    from src.components.structured_output import VulnerabilityType


class IdentifyVulnTypeAgent(BaseVICAgent):
    stage = artifacts.IDENTIFY_VULN_TYPE
    agent_name = "IdentifyVulnTypeAgent"
    system_prompt = IDENTIFY_VULN_TYPE_SYSTEM_PROMPT
    response_format = VulnerabilityType

    def task_message(self, *args, **kwargs) -> str:
        return """
            You will be provided with pre-VIC folder, post-VIC folder, PR data and a diff file between the pre-VIC and post-VIC folder. 
            Your task is to identify the type of vulnerability present in the provided data. Please provide your analysis in a structured format as defined by the VulnerabilityType schema.
        """


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/agent/identify-vuln-type-agent.py <data_name>")
        sys.exit(1)

    data_name = sys.argv[1]
    agent = IdentifyVulnTypeAgent()
    result = agent.run(data_name)
    
    # Extract structural payload for backwards compatibility in console output
    payload = result.get('structured_response') or result.get('structured_output')
    print(f"Final Result: {payload}")
