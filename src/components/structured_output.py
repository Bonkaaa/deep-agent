from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

# SourceSinkAgent structured output model
class Location(BaseModel):
    line: int = Field(..., description="The line number in the source file where the issue is located.")
    column: int = Field(..., description="The column number in the source file where the issue is located.")

class EndPointInfo(BaseModel):
    name: str = Field(..., description="The name of the source or sink.")
    file: str = Field(..., description="The file where the source or sink is located.")
    location: Location = Field(..., description="The location of the source or sink in the file.")

class SourceSinkPair(BaseModel):
    source: EndPointInfo = Field(..., description="Information about the source.")
    sink: EndPointInfo = Field(..., description="Information about the sink.")
    explaination: str = Field(..., description="A detailed explanation of why this source-sink pair is suspicious.")
    rank: int = Field(..., description="The risk rank of this source-sink pair, with 1 being the most risky.")

class SourceSinkAnalysis(BaseModel):
    pairs: List[SourceSinkPair] = Field(..., description="A list of the top 5 most suspicious source-sink pairs identified in the analysis.")

# =============================================

# IdentifyVulnTypeAgent structured output model
class VulnerabilityType(BaseModel):
    name: str = Field(..., description="The name of the vulnerability type.")
    description: str = Field(..., description="A description of why this is a vulnerability.")

# =============================================

# SanitizerAdditionalFlowStepAgent structured output model
class FlowStepType(str, Enum):
    OPAQUE_CALL       = "opaque_call"       # taint = unparse(taintedNode)
    CALLBACK_PARAM    = "callback_param"    # arr.forEach(item => ...)
    PROPERTY_READ     = "property_read"     # obj.prop carries taint out
    RETURN_CAPTURE    = "return_capture"    # outer captures inner's return
    STRING_OPERATION  = "string_operation"  # join, concat, template literal

class SanitizerType(str, Enum):
    VALUE_SANITIZER   = "value_sanitizer"   # taint cleansed at a call
    GUARD_SANITIZER   = "guard_sanitizer"   # typeof/instanceof check
    ALLOWLIST_CHECK   = "allowlist_check"   # value checked against safe set

class AdditionalFlowStep(BaseModel):
    step_type: FlowStepType
    pred_description: str = Field(
        ..., description="Natural language description of the predecessor node — where taint enters this hop."
    )
    succ_description: str = Field(
        ..., description="Natural language description of the successor node — where taint exits this hop."
    )
    pred_code_hint: str = Field(
        ..., description="The actual code expression or pattern acting as pred, e.g. 'unparse.getArgument(0)'."
    )
    succ_code_hint: str = Field(
        ..., description="The actual code expression or pattern acting as succ, e.g. 'DataFlow::exprNode(unparse)'."
    )
    hop_order: int = Field(
        ..., description="Position of this step in the source-to-sink chain, starting at 1."
    )

class Sanitizer(BaseModel):
    sanitizer_type: SanitizerType
    description: str = Field(
        ..., description="Why this node breaks the taint — what it checks or transforms."
    )
    code_hint: str = Field(
        ..., description="The code pattern identifying this sanitizer, e.g. 'sanitizeInput call wrapping the tainted value'."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="How confident the agent is that this is a real sanitizer vs a FP risk. Start low; raise after Stage 7 validation."
    )

class FlowModelingAnalysis(BaseModel):
    additional_flow_steps: List[AdditionalFlowStep] = Field(
        ..., description="Ordered list of isAdditionalFlowStep clauses needed to bridge all taint flow gaps."
    )
    sanitizers: List[Sanitizer] = Field(
        default_factory=list,
        description="Sanitizer nodes, if any"
    )
    needs_taint_tracking: bool = Field(
        ..., description="True if TaintTracking::Global is needed; False if DataFlow::Global suffices."
    )
    reasoning: str = Field(
        ..., description="Free-text chain-of-thought explaining the overall flow modeling strategy."
    )

# =============================================
class GenerationStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"

class QueryGeneration(BaseModel):
    status: GenerationStatus
    query_path: str = Field(..., description="The path to the generated query.")
    query_content: str = Field(..., description="The complete text of the generated CodeQL query.")
    explanation: str = Field(..., description="A detailed explanation of the generated query and how it exposes the vulnerability.")