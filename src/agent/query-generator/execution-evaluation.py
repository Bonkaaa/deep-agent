import asyncio
from pathlib import Path
import json
import os
import sys
from typing import Optional, Dict, Any
from ...utils import collect_tool_calls, setup_logger
from ...config import ROOT_DIR
from dotenv import load_dotenv

try:
    from ...components.compare_results import (
        compare_codeql_results,
        extract_signatures_from_sarif,
        _signature_to_dict,
    )
except ImportError:
    try:
        from src.components.compare_results import (
            compare_codeql_results,
            extract_signatures_from_sarif,
            _signature_to_dict,
        )
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parents[3]))
        from src.components.compare_results import (
            compare_codeql_results,
            extract_signatures_from_sarif,
            _signature_to_dict,
        )

load_dotenv()  # Load environment variables from .env file

logger = setup_logger("compilation-execution-agent.log", "CompilationAndExecutionAgentLogger")

class QueryExecution:
    def __init__(self, query_path: str, data_name: str, database_path: str):
        self.query_path = query_path
        self.data_name = data_name
        self.database_path = database_path
        self.codeql_path = os.getenv("CODEQL_CLI_PATH")

    async def run_query_on_database(
        self, 
        query_path: str, 
        database_path: str,
        iteration: int, 
        output_dir: str = None):

        if output_dir is None:
            output_dir = os.path.dirname(query_path)
        
        base_name = f"{self.data_name}_iteration_{iteration}"

        bqrs_path = os.path.join(output_dir, f"{base_name}_results.bqrs")
        sarif_path = os.path.join(output_dir, f"{base_name}_results.sarif")

        try: 
            await self._run_codeql_query(query_path, database_path, bqrs_path)
            await self._parse_sarif_result(bqrs_path, sarif_path)
            await self._cleanup_cache(database_path)
        except Exception as e:
            logger.error(f"Error during query execution: {str(e)}")
            raise

    async def _run_codeql_query(self, query_path: str, database_path: str, output_path: str):
        cmd = [
            self.codeql_path, "query", "run",
            "--database", database_path,
            "--output", output_path,
            query_path
        ]

        logger.info(f"Running CodeQL query with command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"CodeQL query execution failed with return code {process.returncode}")
            raise RuntimeError(f"CodeQL query execution failed: {stderr.decode()}")
        
    async def _parse_sarif_result(self, bqrs_path: str, output_path):
        cmd = [
            self.codeql_path, "bqrs", "interpret",
            "--format=sarif-latest",
            "-t" "kind=problem", # Check if -t id=... is needed or not. Initally set up only kind = problem cuz all the query should be `kind=problem`
            "--output", output_path,
            bqrs_path
        ]

        logger.info(f"Parsing SARIF result from BQRS file with command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Parsing SARIF result failed with return code {process.returncode}")
            logger.error(f"STDOUT: {stdout.decode()}")
            logger.error(f"Error output: {stderr.decode()}")
            raise RuntimeError(f"Parsing SARIF result failed: {stderr.decode()}")
        
        else:
            logger.info(f"Parsing SARIF result completed successfully. Output written to {output_path}")
            logger.info(f"STDOUT: {stdout.decode()}")
            if os.path.exists(output_path):
                with open(output_path, 'r') as f:
                    sarif_data = json.load(f)
                    logger.info(f"SARIF data: {json.dumps(sarif_data, indent=2)}")
                logger.info(f"SARIF file size: {os.path.getsize(output_path)} bytes")
            else:
                logger.error(f"SARIF output file {output_path} does not exist after parsing.")
                raise FileNotFoundError(f"SARIF output file {output_path} does not exist after parsing.")
        
    async def _cleanup_cache(self, database_dir: str):
        try:
            cmd = [
                self.codeql_path, "database", "cleanup",
                "--cache-cleanup=clear",
                database_dir
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(f"CodeQL database cleanup failed with return code {process.returncode}")
            else:
                logger.info(f"CodeQL database cleanup completed successfully. STDOUT: {stdout.decode()}")

        except Exception as e:
            logger.error(f"Exception during CodeQL database cleanup: {str(e)}")

class QueryResult:
    def __init__(self, success: bool, num_results: int, error: str = ""):
        self.success = success
        self.num_results = num_results
        self.error = error

class Evaluation:
    def __init__(self, sarif_before_path: str, sarif_after_path: str, output_dir: str = None):
        """
        Initialize the Evaluation module.

        Args:
            sarif_before_path (str): Path to the SARIF result file of the clean/fixed version (before).
            sarif_after_path (str): Path to the SARIF result file of the vulnerable version (after).
            output_dir (str, optional): Directory to save output files. Defaults to directory of sarif_after_path.
        """
        self.sarif_before_path = Path(sarif_before_path)
        self.sarif_after_path = Path(sarif_after_path)
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.sarif_after_path.parent
            
    def _generate_evaluation_summary(
        self, 
        vuln_result: QueryResult, 
        fixed_result: QueryResult, 
        diff_result: Optional[Dict],
        iteration_number: int
    ) -> str:
        """Generate execution and differential summary"""
        
        lines = [f"## Query Evaluation Summary (Iteration {iteration_number})"]
        # Execution status
        if not vuln_result.success or not fixed_result.success:
            lines.append("EXECUTION FAILED")
            if not vuln_result.success:
                lines.append(f"  Vulnerable DB: {vuln_result.error}")
            if not fixed_result.success:
                lines.append(f"  Fixed DB: {fixed_result.error}")
            return "\n".join(lines)
        
        # Basic result counts
        lines.append(f"Results: Vulnerable={vuln_result.num_results}, Fixed={fixed_result.num_results}")

        def format_diff_entry(entry: Dict[str, Any]) -> str:
            if "source_text" in entry or "sink_text" in entry:
                return (
                    f"Rule: {entry.get('rule_id')} | "
                    f"Source: {entry.get('source_text')} | Source Columns: {entry.get('source_start_col')}-{entry.get('source_end_col')} | "
                    f"Sink: {entry.get('sink_text')} | Sink Columns: {entry.get('sink_start_col')}-{entry.get('sink_end_col')}"
                )

            return (
                f"Rule: {entry.get('rule_id')} | "
                f"Message: {entry.get('message')} | "
                f"URI: {entry.get('uri')} | "
                f"Line: {entry.get('start_line')} | "
                f"Col: {entry.get('start_column')}"
            )

        if diff_result:
            only_in_before = diff_result.get("only_in_before", [])
            only_in_after = diff_result.get("only_in_after", [])
            common = diff_result.get("common", [])

            lines.append("Differential comparison: before = fixed, after = vulnerable")
            lines.append(f"Shared signatures: {len(common)}")
            # only_in_before = signatures present only in the BEFORE file (fixed)
            # only_in_after = signatures present only in the AFTER file (vulnerable)
            lines.append(f"Only in fixed (before): {len(only_in_before)}")
            lines.append(f"Only in vulnerable (after): {len(only_in_after)}")

            if only_in_before:
                lines.append("Findings only in fixed (before):")
                for bug in only_in_before:
                    lines.append(f"  - {format_diff_entry(bug)}")

            if only_in_after:
                lines.append("Findings only in vulnerable (after):")
                for bug in only_in_after:
                    lines.append(f"  - {format_diff_entry(bug)}")

            if not only_in_before and not only_in_after:
                lines.append("No differential findings detected between the two versions.")
        else:
            lines.append("Differential comparison unavailable.")
        
        return "\n".join(lines)

    def run_evaluation(self, iteration_number: int) -> bool:
        """
        Compare the results, find unique bugs, save files, and determine success.
        
        Returns:
            bool: True if evaluation is successful (vuln_result > fixed_result and both ran successfully).
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Parse Fixed (Before) SARIF
        fixed_success = True
        fixed_error = ""
        fixed_signatures = set()
        
        if not self.sarif_before_path.exists():
            fixed_success = False
            fixed_error = f"SARIF file not found at {self.sarif_before_path}"
        else:
            try:
                fixed_signatures = extract_signatures_from_sarif(self.sarif_before_path)
            except Exception as e:
                fixed_success = False
                fixed_error = f"Failed to extract signatures: {str(e)}"
                
        fixed_result = QueryResult(
            success=fixed_success,
            num_results=len(fixed_signatures) if fixed_success else 0,
            error=fixed_error
        )
        
        # 2. Parse Vulnerable (After) SARIF
        vuln_success = True
        vuln_error = ""
        vuln_signatures = set()
        
        if not self.sarif_after_path.exists():
            vuln_success = False
            vuln_error = f"SARIF file not found at {self.sarif_after_path}"
        else:
            try:
                vuln_signatures = extract_signatures_from_sarif(self.sarif_after_path)
            except Exception as e:
                vuln_success = False
                vuln_error = f"Failed to extract signatures: {str(e)}"
                
        vuln_result = QueryResult(
            success=vuln_success,
            num_results=len(vuln_signatures) if vuln_success else 0,
            error=vuln_error
        )
        
        # 3. Perform comparison if both succeeded
        diff_result = None
        is_success = False
        
        if fixed_success and vuln_success:
            only_in_after = sorted(vuln_signatures - fixed_signatures)
            only_in_before = sorted(fixed_signatures - vuln_signatures)
            common = sorted(fixed_signatures & vuln_signatures)
            
            diff_result = {
                "only_in_before": [_signature_to_dict(sig) for sig in only_in_before],
                "only_in_after": [_signature_to_dict(sig) for sig in only_in_after],
                "common": [_signature_to_dict(sig) for sig in common],
            }
            
            is_success = vuln_result.num_results > fixed_result.num_results
            
            # Extract unique bugs in after/vulnerable version to a JSON file
            unique_bugs_file = self.output_dir / f"unique_bugs_after_iteration_{iteration_number}.json"
            try:
                with open(unique_bugs_file, "w", encoding="utf-8") as f:
                    json.dump(diff_result["only_in_after"], f, indent=2, ensure_ascii=False)
                logger.info(f"Successfully extracted unique after bugs to {unique_bugs_file}")
            except Exception as e:
                logger.error(f"Failed to write unique bugs JSON: {str(e)}")
        else:
            is_success = False
            
        # 4. Generate summary and write to text file
        summary_text = self._generate_evaluation_summary(
            vuln_result=vuln_result,
            fixed_result=fixed_result,
            diff_result=diff_result,
            iteration_number=iteration_number
        )
        
        summary_file = self.output_dir / f"evaluation_summary_iteration_{iteration_number}.txt"
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary_text)
            logger.info(f"Successfully wrote evaluation summary to {summary_file}")
        except Exception as e:
            logger.error(f"Failed to write evaluation summary text: {str(e)}")
            
        return is_success
