from pathlib import Path
from ..utils import setup_logger
from ..config import ROOT_DIR
from ..components.get_llm import get_llm

logger = setup_logger("summary-agent.log", "SummaryAgentLogger")

class SummaryAgent:
    def __init__(self, data_name: str):
        self.data_name = data_name
        self.llm = get_llm()

    def run(self, vuln_type: str, source_sink_results: str, sanitizer_results: str, query_content: str, eval_summary: str) -> str:
        """
        Generates a developer-friendly vulnerability report using the LLM.
        """
        logger.info(f"Generating summary report for {self.data_name}...")
        
        prompt = f"""
You are a senior security engineer. Your task is to write a comprehensive, developer-friendly review report summarizing the vulnerability discovery and verification results.

Vulnerability Type:
{vuln_type}

Source-Sink Pairs:
{source_sink_results}

Sanitizers & Additional Flow Steps:
{sanitizer_results}

Generated CodeQL Query:
```ql
{query_content}
```

Evaluation differential test results:
{eval_summary}

Based on this information, write a structured Markdown report including:
1. Executive Summary: What was found and the severity/impact.
2. Taint Flow details: Explanation of the source, sink, and intermediate propagation steps.
3. CodeQL Verification: Confirmation of the query successfully compiling and flagging the vulnerable version but not the clean version.
4. Remediation suggestions: How developers should fix this vulnerability (e.g., using proper sanitizers or validation).

Provide only the Markdown content.
"""
        
        response = self.llm.invoke(prompt)
        report_content = response.content if hasattr(response, 'content') else str(response)
        
        # Save output
        output_dir = Path(ROOT_DIR) / "output" / self.data_name
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / f"{self.data_name}_vulnerability_report.md"
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        logger.info(f"Summary report written to {report_file}")
        return report_content
