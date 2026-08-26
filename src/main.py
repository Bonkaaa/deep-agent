import asyncio
import os
import sys
import json
import importlib.util
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from src.utils import setup_logger

logger = setup_logger("orchestrator.log", "OrchestratorLogger")
load_dotenv()

# Helper to import hyphenated files dynamically
def import_hyphenated_module(module_name: str, file_path: Path, package_name: str = "src.agent"):
    spec = importlib.util.spec_from_file_location(f"{package_name}.{module_name}", str(file_path))
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package_name
    sys.modules[f"{package_name}.{module_name}"] = module
    spec.loader.exec_module(module)
    return module

# Resolve CodeQL path
codeql_cli_dir = os.getenv("CODEQL_CLI_PATH", r"C:\Program Files\codeql").strip("'").strip('"')
codeql_exe = os.path.join(codeql_cli_dir, "codeql.exe")

def detect_language(data_dir: Path) -> str:
    extensions = {
        ".js": "javascript",
        ".ts": "javascript",
        ".py": "python",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "cpp",
        ".go": "go",
        ".cs": "csharp",
        ".rb": "ruby",
    }
    for ext, lang in extensions.items():
        if list(data_dir.glob(f"**/*{ext}")):
            return lang
    return "javascript"  # Default fallback

async def create_codeql_database(db_path: Path, source_path: Path, language: str):
    logger.info(f"Creating CodeQL database at {db_path} for language: {language}...")
    if db_path.exists():
        logger.info(f"Database directory {db_path} already exists. Cleaning up first...")
        import shutil
        shutil.rmtree(db_path)

    cmd = [
        codeql_exe, "database", "create",
        str(db_path),
        f"--source-root={source_path}",
        f"--language={language}"
    ]
    logger.info(f"Running command: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"Database creation failed: {stderr.decode()}")
        raise RuntimeError(f"Database creation failed: {stderr.decode()}")
    logger.info(f"Successfully created CodeQL database at {db_path}")

def get_structured_response(res):
    if not res:
        return None
    if isinstance(res, dict):
        return res.get("structured_response") or res.get("structured_output") or res
    return res

async def main(data_name: str, max_iterations: int = 3):
    logger.info(f"Starting orchestration pipeline for VIC: {data_name} (max iterations: {max_iterations})")
    
    # 0. Set up paths
    data_dir = ROOT_DIR / "data" / data_name
    before_src = data_dir / "before"
    after_src = data_dir / "after"
    
    before_db_path = data_dir / "before_db"
    after_db_path = data_dir / "after_db"
    
    # 1. Detect language and build databases if missing
    language = detect_language(after_src)
    logger.info(f"Detected programming language: {language}")
    
    if not (before_db_path / "codeql-database.yml").exists():
        await create_codeql_database(before_db_path, before_src, language)
    else:
        logger.info(f"Clean (before) CodeQL database already exists.")
        
    if not (after_db_path / "codeql-database.yml").exists():
        await create_codeql_database(after_db_path, after_src, language)
    else:
        logger.info(f"Vulnerable (after) CodeQL database already exists.")
        
    # Load dynamic agents
    identify_agent_file = ROOT_DIR / "src" / "agent" / "identify-vuln-type-agent.py"
    source_sink_agent_file = ROOT_DIR / "src" / "agent" / "source-sink-agent.py"
    sanitizer_agent_file = ROOT_DIR / "src" / "agent" / "sanitizer-additionalFlowStep-agent.py"
    query_gen_agent_file = ROOT_DIR / "src" / "agent" / "query-generator" / "query-generate-agent.py"
    execution_eval_file = ROOT_DIR / "src" / "agent" / "query-generator" / "execution-evaluation.py"
    
    identify_module = import_hyphenated_module("identify_vuln_type_agent", identify_agent_file, package_name="src.agent")
    source_sink_module = import_hyphenated_module("source_sink_agent", source_sink_agent_file, package_name="src.agent")
    sanitizer_module = import_hyphenated_module("sanitizer_additional_flow_step_agent", sanitizer_agent_file, package_name="src.agent")
    query_gen_module = import_hyphenated_module("query_generate_agent", query_gen_agent_file, package_name="src.agent.query_generator")
    execution_eval_module = import_hyphenated_module("execution_evaluation", execution_eval_file, package_name="src.agent.query_generator")
    
    # 2. Stage 1: Identify Vulnerability Type
    logger.info("Executing IdentifyVulnTypeAgent...")
    identify_agent = identify_module.IdentifyVulnTypeAgent()
    identify_res = identify_agent.run(data_name)
    structured_identify = get_structured_response(identify_res)
    
    if not structured_identify:
        logger.error("IdentifyVulnTypeAgent did not return a valid result.")
        sys.exit(1)
        
    vuln_type = structured_identify.name
    vuln_desc = structured_identify.description
    logger.info(f"Vulnerability Type Identified: {vuln_type}")
    
    # 3. Stage 2: Identify Source-Sink Pairs
    logger.info("Executing SourceSinkAgent...")
    source_sink_agent = source_sink_module.SourceSinkAgent(data_name)
    source_sink_res = source_sink_agent.run(vuln_type)
    structured_source_sink = get_structured_response(source_sink_res)
    
    if not structured_source_sink:
        logger.error("SourceSinkAgent did not return a valid result.")
        sys.exit(1)
        
    # Write the result to the destination directory for the sanitizer agent
    dest_dir = data_dir / "source-sink-agent_output"
    dest_dir.mkdir(parents=True, exist_ok=True)
    source_sink_text_file = dest_dir / "source_sink_analysis.txt"
    
    source_sink_text = ""
    for pair in structured_source_sink.pairs:
        source_sink_text += f"Rank: {pair.rank}\n"
        source_sink_text += f"Source: {pair.source.name} in {pair.source.file} (Line: {pair.source.location.line}, Col: {pair.source.location.column})\n"
        source_sink_text += f"Sink: {pair.sink.name} in {pair.sink.file} (Line: {pair.sink.location.line}, Col: {pair.sink.location.column})\n"
        source_sink_text += f"Explanation: {pair.explaination}\n\n"
        
    with open(source_sink_text_file, "w", encoding="utf-8") as f:
        f.write(source_sink_text)
    logger.info(f"Saved source-sink analysis output to {source_sink_text_file}")
    
    # 4. Stage 3: Sanitizers and additionalFlowSteps identification
    logger.info("Executing SanitizerAdditionalFlowStepAgent...")
    sanitizer_agent = sanitizer_module.SanitizerAdditionalFlowStepAgent(data_name)
    sanitizer_res = sanitizer_agent.run(vuln_type)
    structured_sanitizer = get_structured_response(sanitizer_res)
    
    if not structured_sanitizer:
        logger.error("SanitizerAdditionalFlowStepAgent did not return a valid result.")
        sys.exit(1)
        
    sanitizers_text = ""
    if hasattr(structured_sanitizer, "sanitizers"):
        for s in structured_sanitizer.sanitizers:
            sanitizers_text += f"- Type: {s.sanitizer_type}\n  Description: {s.description}\n  Code Hint: {s.code_hint}\n"
            
    flow_steps_text = ""
    if hasattr(structured_sanitizer, "additional_flow_steps"):
        for step in structured_sanitizer.additional_flow_steps:
            flow_steps_text += f"- Order {step.hop_order} | Type: {step.step_type}\n"
            flow_steps_text += f"  Predecessor: {step.pred_description} ({step.pred_code_hint})\n"
            flow_steps_text += f"  Successor: {step.succ_description} ({step.succ_code_hint})\n"

    # 5. Query Generation & Refinement Loop
    logger.info("Entering Query Generation & Differential Validation Loop...")
    query_gen_agent = query_gen_module.QueryGenerateAgent()
    
    feedback = None
    final_eval_summary = ""
    final_query_content = ""
    
    output_dir = ROOT_DIR / "output" / data_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(1, max_iterations + 1):
        logger.info(f"Loop Iteration {i}/{max_iterations}...")
        
        # Prepare context payload for the query generator
        context_payload = f"""
Vulnerability Type: {vuln_type}
Vulnerability Description: {vuln_desc}

Identified Source-Sink Pairs:
{source_sink_text}

Sanitizer & Flow Modeling Analysis:
Sanitizers:
{sanitizers_text if sanitizers_text else "None"}
Additional Flow Steps:
{flow_steps_text if flow_steps_text else "None"}
Needs Taint Tracking: {structured_sanitizer.needs_taint_tracking if hasattr(structured_sanitizer, 'needs_taint_tracking') else 'True'}
Reasoning: {structured_sanitizer.reasoning if hasattr(structured_sanitizer, 'reasoning') else ''}
"""
        
        # Add feedback from previous iterations if any
        if feedback:
            context_payload += f"\nPrevious Run Failure Feedback:\n{feedback}\nPlease refine the CodeQL query to fix this."
            
        # Run QueryGenerateAgent
        logger.info("Generating CodeQL query...")
        gen_res = await query_gen_agent.run(data_name, feedback=context_payload, thread_id=f"query_gen_thread_{data_name}")
        structured_gen = get_structured_response(gen_res)
        
        if not structured_gen or not structured_gen.query_content:
            logger.error("QueryGenerateAgent did not return a valid query.")
            feedback = "Query generation returned empty query or failed."
            continue
            
        final_query_content = structured_gen.query_content
        target_query_path = output_dir / f"query_iteration_{i}.ql"
        
        # Write query content to file
        with open(target_query_path, "w", encoding="utf-8") as f:
            f.write(final_query_content)
        logger.info(f"Saved generated query to {target_query_path}")
        
        # Compile and execute query on both databases
        logger.info("Executing generated query on clean (before) and vulnerable (after) databases...")
        
        before_run_dir = output_dir / f"before_iter_{i}"
        after_run_dir = output_dir / f"after_iter_{i}"
        
        before_run_dir.mkdir(parents=True, exist_ok=True)
        after_run_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            executor_before = execution_eval_module.QueryExecution(
                query_path=str(target_query_path),
                data_name=data_name,
                database_path=str(before_db_path)
            )
            await executor_before.run_query_on_database(
                query_path=str(target_query_path),
                database_path=str(before_db_path),
                iteration=i,
                output_dir=str(before_run_dir)
            )
            
            executor_after = execution_eval_module.QueryExecution(
                query_path=str(target_query_path),
                data_name=data_name,
                database_path=str(after_db_path)
            )
            await executor_after.run_query_on_database(
                query_path=str(target_query_path),
                database_path=str(after_db_path),
                iteration=i,
                output_dir=str(after_run_dir)
            )
            
            # Evaluate results
            sarif_before = before_run_dir / f"{data_name}_iteration_{i}_results.sarif"
            sarif_after = after_run_dir / f"{data_name}_iteration_{i}_results.sarif"
            
            evaluator = execution_eval_module.Evaluation(
                sarif_before_path=str(sarif_before),
                sarif_after_path=str(sarif_after),
                output_dir=str(output_dir)
            )
            
            is_success = evaluator.run_evaluation(iteration_number=i)
            
            # Read generated summary
            summary_txt_file = output_dir / f"evaluation_summary_iteration_{i}.txt"
            if summary_txt_file.exists():
                with open(summary_txt_file, "r", encoding="utf-8") as f:
                    final_eval_summary = f.read()
            else:
                final_eval_summary = f"Evaluation completed. Success: {is_success}."
                
            if is_success:
                logger.info(f"Query verification succeeded on iteration {i}!")
                break
            else:
                logger.info(f"Query verification failed on iteration {i}. Checking results comparison...")
                feedback = final_eval_summary
                
        except Exception as e:
            logger.error(f"Error during query execution/compilation: {str(e)}")
            feedback = f"CodeQL query failed to compile or run successfully. Error:\n{str(e)}"
            final_eval_summary = f"Iteration {i} execution error: {str(e)}"
            
    # 6. Stage 5: Summary Agent Report
    logger.info("Executing SummaryAgent...")
    from src.agent.summary_agent import SummaryAgent
    summary_agent = SummaryAgent(data_name)
    report = summary_agent.run(
        vuln_type=vuln_type,
        source_sink_results=source_sink_text,
        sanitizer_results=f"Sanitizers:\n{sanitizers_text}\nAdditional Flow Steps:\n{flow_steps_text}",
        query_content=final_query_content,
        eval_summary=final_eval_summary
    )
    
    logger.info("Multi-agent vulnerability validation completed successfully!")
    print("\n" + "="*40 + "\nREPORT COMPLETED\n" + "="*40)
    print(report)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <data_name> [max_iterations]")
        sys.exit(1)
        
    vic_name = sys.argv[1]
    max_iters = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    asyncio.run(main(vic_name, max_iters))
