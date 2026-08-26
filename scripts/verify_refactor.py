import sys
import importlib.util
from pathlib import Path
from pydantic import BaseModel

# Add project root to sys.path
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from src import artifacts
from src.agent.base import BaseVICAgent, AsyncVICAgent, AgentOutputError
from src.components.structured_output import VulnerabilityType, SourceSinkAnalysis, FlowModelingAnalysis, QueryGeneration


def import_hyphenated_module(module_name: str, file_path: Path, package_name: str = "src.agent"):
    spec = importlib.util.spec_from_file_location(f"{package_name}.{module_name}", str(file_path))
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package_name
    sys.modules[f"{package_name}.{module_name}"] = module
    spec.loader.exec_module(module)
    return module


# Load the refactored agents dynamically
identify_agent_file = ROOT_DIR / "src" / "agent" / "identify-vuln-type-agent.py"
source_sink_agent_file = ROOT_DIR / "src" / "agent" / "source-sink-agent.py"
sanitizer_agent_file = ROOT_DIR / "src" / "agent" / "sanitizer-additionalFlowStep-agent.py"
query_gen_agent_file = ROOT_DIR / "src" / "agent" / "query-generator" / "query-generate-agent.py"

identify_module = import_hyphenated_module("identify_vuln_type_agent", identify_agent_file)
source_sink_module = import_hyphenated_module("source_sink_agent", source_sink_agent_file)
sanitizer_module = import_hyphenated_module("sanitizer_additional_flow_step_agent", sanitizer_agent_file)
query_gen_module = import_hyphenated_module("query_generate_agent", query_gen_agent_file, package_name="src.agent.query_generator")

IdentifyVulnTypeAgent = identify_module.IdentifyVulnTypeAgent
SourceSinkAgent = source_sink_module.SourceSinkAgent
SanitizerAdditionalFlowStepAgent = sanitizer_module.SanitizerAdditionalFlowStepAgent
QueryGenerateAgent = query_gen_module.QueryGenerateAgent


def test_classes_contract():
    print("Testing agent contract attributes...")
    agents = [
        (IdentifyVulnTypeAgent, artifacts.IDENTIFY_VULN_TYPE, "IdentifyVulnTypeAgent", VulnerabilityType),
        (SourceSinkAgent, artifacts.SOURCE_SINK, "SourceSinkIdentificationAgent", SourceSinkAnalysis),
        (SanitizerAdditionalFlowStepAgent, artifacts.SANITIZER_FLOW_STEP, "SanitizerAdditionalFlowStepAgent", FlowModelingAnalysis),
        (QueryGenerateAgent, artifacts.QUERY_GENERATE, "QueryGenerateAgent", QueryGeneration),
    ]

    for cls, expected_stage, expected_name, expected_schema in agents:
        print(f"Checking class: {cls.__name__}")
        assert cls.stage == expected_stage, f"{cls.__name__}.stage is {cls.stage}, expected {expected_stage}"
        assert cls.agent_name == expected_name, f"{cls.__name__}.agent_name is {cls.agent_name}, expected {expected_name}"
        assert cls.response_format == expected_schema, f"{cls.__name__}.response_format is {cls.response_format}, expected {expected_schema}"
        assert cls.system_prompt, f"{cls.__name__}.system_prompt is empty"
    print("All class contracts verified successfully!")


def test_skill_dirs():
    print("Testing skill directories resolving...")
    identify = IdentifyVulnTypeAgent()
    assert identify.skill_dir.exists(), f"Skill directory not found: {identify.skill_dir}"

    source_sink = SourceSinkAgent("flat_5.0.0")
    assert source_sink.skill_dir.exists(), f"Skill directory not found: {source_sink.skill_dir}"

    sanitizer = SanitizerAdditionalFlowStepAgent("flat_5.0.0")
    assert sanitizer.skill_dir.exists(), f"Skill directory not found: {sanitizer.skill_dir}"

    query_gen = QueryGenerateAgent()
    assert query_gen.skill_dir.exists(), f"Skill directory not found: {query_gen.skill_dir}"
    
    print("All skill directories validated successfully!")


def test_sanitizer_routes():
    print("Testing Sanitizer additional routes...")
    sanitizer = SanitizerAdditionalFlowStepAgent("flat_5.0.0")
    routes = sanitizer.extra_routes()
    assert "/source-sink-agent_output/" in routes, "SanitizerAgent missing '/source-sink-agent_output/' route"
    route = routes["/source-sink-agent_output/"]
    expected_path = ROOT_DIR / "data" / "flat_5.0.0" / "source-sink-agent_output"
    assert Path(route.cwd).resolve() == expected_path.resolve(), f"Route cwd mismatch: {route.cwd} vs {expected_path}"
    print("Sanitizer routes verified successfully!")


def test_extract_compatibility():
    print("Testing _extract backward-compatibility support...")
    class MockAgent(BaseVICAgent):
        stage = "identify-vuln-type"
        agent_name = "MockAgent"
        system_prompt = "Mock"
        response_format = VulnerabilityType
        def task_message(self, *args, **kwargs):
            return "Mock"

    agent = MockAgent()
    
    # Test valid model parsing from dict under structured_response
    mock_res_1 = {"structured_response": {"name": "SQL Injection", "description": "Desc"}}
    res = agent._extract(mock_res_1)
    assert isinstance(res, VulnerabilityType)
    assert res.name == "SQL Injection"

    # Test valid model parsing from dict under structured_output
    mock_res_2 = {"structured_output": {"name": "Path Traversal", "description": "Desc"}}
    res = agent._extract(mock_res_2)
    assert isinstance(res, VulnerabilityType)
    assert res.name == "Path Traversal"

    # Test model validation errors
    try:
        agent._extract({"structured_response": {"invalid": "field"}})
        raise AssertionError("Expected AgentOutputError for invalid schema")
    except Exception as e:
        if isinstance(e, AssertionError):
            raise

    # Test missing payload key
    try:
        agent._extract({"other_key": "some_value"})
        raise AssertionError("Expected AgentOutputError for missing payload keys")
    except AgentOutputError:
        pass
    print("_extract backward-compatibility tests passed!")


def test_legacy_results_read():
    print("Testing legacy results read via artifacts registry...")
    # flat_5.0.0 has a legacy parsed_source_sink_pairs.json
    try:
        result = artifacts.read_result("flat_5.0.0", artifacts.SOURCE_SINK, SourceSinkAnalysis)
        assert len(result.pairs) > 0, "Expected non-empty list of source-sink pairs from legacy file"
        print(f"Successfully read legacy result: found {len(result.pairs)} source-sink pairs.")
    except Exception as e:
        print(f"Failed to read legacy result: {e}")
        raise
    print("Legacy results validation passed!")


if __name__ == "__main__":
    try:
        test_classes_contract()
        test_skill_dirs()
        test_sanitizer_routes()
        test_extract_compatibility()
        test_legacy_results_read()
        print("--- ALL SMOKE TESTS PASSED SUCCESSFULLY! ---")
        sys.exit(0)
    except AssertionError as e:
        print(f"Smoke Test Failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
