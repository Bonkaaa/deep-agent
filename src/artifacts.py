"""Central registry for every file the pipeline reads or writes.

No stage should ever build an output path by hand. Stages ask this module
where things live, which means a path can only be wrong in one place instead
of five, and a producer and its consumer cannot drift apart.

Layout::

    output/<vic>/
      identify-vuln-type/            result.json, tool_calls.json
      source-sink/                   result.json, tool_calls.json
      sanitizer-additional-flow-step/result.json, tool_calls.json
      query-generate/                result_iter_N.json, tool_calls_iter_N.json,
                                     query_iter_N.ql
      evaluation/                    results_<snapshot>_iter_N.bqrs/.sarif,
                                     unique_bugs_iter_N.json,
                                     summary_iter_N.txt

Results are always written as validated JSON via ``model_dump_json`` and read
back through ``model_validate_json``, so a malformed artifact fails at the
boundary rather than three stages later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Type, TypeVar

from pydantic import BaseModel

try:
    from .config import ROOT_DIR
except ImportError:  # running from a directly-executed script
    from src.config import ROOT_DIR

ROOT_DIR = Path(ROOT_DIR)

M = TypeVar("M", bound=BaseModel)

# --- canonical stage names -------------------------------------------------
# These strings are the single source of truth. They name the output
# directory, the skill directory, the log file and the checkpoint thread.

IDENTIFY_VULN_TYPE = "identify-vuln-type"
SOURCE_SINK = "source-sink"
SANITIZER_FLOW_STEP = "sanitizer-additional-flow-step"
QUERY_GENERATE = "query-generate"
EVALUATION = "evaluation"

STAGES = (
    IDENTIFY_VULN_TYPE,
    SOURCE_SINK,
    SANITIZER_FLOW_STEP,
    QUERY_GENERATE,
    EVALUATION,
)

#: Stages that run more than once inside the refine loop. Their artifacts
#: carry an ``_iter_N`` suffix; the others do not.
ITERATIVE_STAGES = frozenset({QUERY_GENERATE, EVALUATION})

#: Filename stem and extension for each kind of artifact.
_KINDS: dict[str, tuple[str, str]] = {
    "result": ("result", ".json"),
    "tool_calls": ("tool_calls", ".json"),
    "query": ("query", ".ql"),
    "bqrs": ("results", ".bqrs"),
    "sarif": ("results", ".sarif"),
    "unique_bugs": ("unique_bugs", ".json"),
    "summary": ("summary", ".txt"),
}


class ArtifactNotFound(FileNotFoundError):
    """Raised when a stage asks for an upstream artifact that was never written."""


def _check_stage(stage: str) -> str:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage {stage!r}. Expected one of {list(STAGES)}.")
    return stage


def _suffix(stage: str, iteration: int) -> str:
    return f"_iter_{iteration}" if stage in ITERATIVE_STAGES else ""


def vic_dir(vic: str) -> Path:
    """Root output directory for one VIC."""
    return ROOT_DIR / "output" / vic


def stage_dir(vic: str, stage: str, create: bool = False) -> Path:
    """Directory holding every artifact produced by ``stage`` for ``vic``.

    Also the mount point a downstream agent should expose to read the stage's
    output, which is what keeps producer and consumer in agreement.
    """
    path_ = vic_dir(vic) / _check_stage(stage)
    if create:
        path_.mkdir(parents=True, exist_ok=True)
    return path_


def path(vic: str, stage: str, kind: str, iteration: int = 1) -> Path:
    """Absolute path of a single artifact.

    Args:
        vic: dataset entry name, e.g. ``"flat_5.0.0"``.
        stage: one of :data:`STAGES`.
        kind: one of ``result``, ``tool_calls``, ``query``, ``bqrs``,
            ``sarif``, ``unique_bugs``, ``summary``.
        iteration: refine-loop iteration; ignored for non-iterative stages.
    """
    if kind not in _KINDS:
        raise ValueError(f"Unknown artifact kind {kind!r}. Expected one of {sorted(_KINDS)}.")
    stem, ext = _KINDS[kind]
    return stage_dir(vic, stage) / f"{stem}{_suffix(stage, iteration)}{ext}"


def _check_snapshot(snapshot: str) -> str:
    if snapshot not in ("before", "after"):
        raise ValueError(f"snapshot must be 'before' or 'after', got {snapshot!r}")
    return snapshot


def sarif_path(vic: str, snapshot: str, iteration: int = 1) -> Path:
    """SARIF path for one snapshot. ``snapshot`` is ``"before"`` or ``"after"``.

    Mirrors the evaluation convention: before = fixed, after = vulnerable.
    """
    return stage_dir(vic, EVALUATION) / f"results_{_check_snapshot(snapshot)}_iter_{iteration}.sarif"


def bqrs_path(vic: str, snapshot: str, iteration: int = 1) -> Path:
    """BQRS path for one snapshot. See :func:`sarif_path`."""
    return stage_dir(vic, EVALUATION) / f"results_{_check_snapshot(snapshot)}_iter_{iteration}.bqrs"


def exists(vic: str, stage: str, kind: str = "result", iteration: int = 1) -> bool:
    """True if the artifact is on disk. Use for resumable batch runs."""
    return path(vic, stage, kind, iteration).exists()


# --- writing ---------------------------------------------------------------

def write_result(vic: str, stage: str, model: BaseModel, iteration: int = 1) -> Path:
    """Serialise a stage's structured response as validated JSON."""
    target = path(vic, stage, "result", iteration)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model, BaseModel):
        payload = model.model_dump_json(indent=2)
    else:  # a plain dict/list still round-trips cleanly
        payload = json.dumps(model, indent=2, ensure_ascii=False, default=str)
    target.write_text(payload, encoding="utf-8")
    return target


def write_tool_calls(vic: str, stage: str, tool_calls: Iterable[Any], iteration: int = 1) -> Path:
    """Persist the agent's tool-call trace for audit."""
    target = path(vic, stage, "tool_calls", iteration)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(list(tool_calls), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return target


def write_text(vic: str, stage: str, kind: str, text: str, iteration: int = 1) -> Path:
    """Write a text artifact (``query``, ``summary``)."""
    target = path(vic, stage, kind, iteration)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def write_json(vic: str, stage: str, kind: str, data: Any, iteration: int = 1) -> Path:
    """Write a raw JSON artifact (``unique_bugs``)."""
    target = path(vic, stage, kind, iteration)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return target


# --- reading ---------------------------------------------------------------

def read_result(vic: str, stage: str, schema: Type[M], iteration: int = 1) -> M:
    """Read and validate an upstream stage's result.

    Raises:
        ArtifactNotFound: the stage has not run yet.
        pydantic.ValidationError: the artifact does not match ``schema``.
    """
    target = path(vic, stage, "result", iteration)
    if not target.exists():
        legacy = _legacy_result(vic, stage)
        if legacy is None:
            raise ArtifactNotFound(
                f"No {stage} result for {vic!r} at {target}. Run the {stage} stage first."
            )
        return schema.model_validate(legacy)
    return schema.model_validate_json(target.read_text(encoding="utf-8"))


def read_text(vic: str, stage: str, kind: str, iteration: int = 1) -> str:
    """Read a text artifact, e.g. an evaluation summary to feed back as guidance."""
    target = path(vic, stage, kind, iteration)
    if not target.exists():
        raise ArtifactNotFound(f"No {kind} artifact for {vic!r} {stage} at {target}.")
    return target.read_text(encoding="utf-8")


def _legacy_result(vic: str, stage: str) -> Any | None:
    """Recover results produced before this registry existed.

    Earlier runs wrote ``output/<vic>/parsed_source_sink_pairs.json`` as a bare
    list. Keeps the existing dataset runs readable; returns None if there is
    nothing to recover.
    """
    if stage != SOURCE_SINK:
        return None
    candidate = vic_dir(vic) / "parsed_source_sink_pairs.json"
    if not candidate.exists():
        return None
    data = json.loads(candidate.read_text(encoding="utf-8"))
    return {"pairs": data} if isinstance(data, list) else data
