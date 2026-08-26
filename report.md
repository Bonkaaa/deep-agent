# `deep_agent` — Repository Report

> An LLM multi-agent pipeline that reads a **vulnerability-inducing commit (VIC)** and automatically authors a **CodeQL** query that detects the vulnerability that commit introduced — then proves the query works by running it against the vulnerable and fixed snapshots and requiring more findings on the vulnerable one.

- **Repository:** `c:\deep_agent`
- **Branch surveyed:** `agent` (others: `main`, `mcp`, `source-sink`)
- **Report date:** 2026-07-29
- **Status:** research prototype / work in progress (see [Current State & Known Gaps](#8-current-state--known-gaps))

---

## 1. What This Repo Does

The repo automates a task that is normally done by hand by a security engineer with CodeQL expertise:

> *Given a commit that introduced a vulnerability, write a static-analysis query that flags it.*

The input is a **VIC dataset entry** — three artifacts describing one commit:

| Artifact | Meaning |
| --- | --- |
| `before/` | source tree **before** the vulnerability was introduced (clean / fixed) |
| `after/` | source tree **after** the vulnerability was introduced (vulnerable) |
| `diff.diff` | the unified diff between the two |

The output is a `.ql` CodeQL query plus an evaluation verdict on whether that query actually distinguishes the two snapshots.

Between input and output sit **four LLM agents** and **one deterministic verification harness**. Each agent is a `deepagents` "deep agent" driven by Gemini, constrained to a Pydantic response schema, and given a virtual filesystem containing the VIC and a markdown *skill* describing its job. The final harness is plain Python + the CodeQL CLI — no LLM — so the pass/fail signal is objective.

### The core evaluation idea

Everything hinges on one line in [execution-evaluation.py:308](src/agent/query-generator/execution-evaluation.py#L308):

```python
is_success = vuln_result.num_results > fixed_result.num_results
```

A generated query is only accepted if it produces **strictly more taint-path findings on the vulnerable snapshot than on the fixed snapshot**. This is a *differential* criterion, and it is deliberately stronger than "the query returns something":

- A query that flags nothing is rejected (0 > 0 is false).
- A query that flags everything everywhere is rejected (equal counts on both snapshots).
- Only a query that is *sensitive to the change the commit made* passes.

That criterion is what turns a fuzzy generative task into a measurable one, and it is the conceptual centre of the whole repo.

---

## 2. Context & Domain

The repo sits at the intersection of three areas:

**Static application security testing (SAST) with CodeQL.**
CodeQL models a codebase as a database and lets you query it in the QL language. Detecting an injection-style bug means writing a **taint-tracking** query: declare *sources* (where attacker-controlled data enters), *sinks* (dangerous operations), optional *sanitizers* (things that neutralise taint), and optional `isAdditionalFlowStep` clauses (extra hops the built-in flow model does not know about). Writing these well is expert work — the repo's premise is that an LLM given the right scaffolding, tools and feedback loop can do it.

**Vulnerability-inducing commit research.**
Rather than "find bugs in this repo," the framing is "here is the exact commit that broke it — characterise it." The before/after pair provides ground truth, which is what makes automated scoring possible at all. This is the standard setup in benchmark-driven vulnerability-detection research.

**Agentic LLM systems.**
Each stage is a `deepagents` agent with a scoped virtual filesystem, a Pydantic-typed response, a markdown skill file for procedure, and (for the query author) a curated allowlist of MCP tools. The design consistently favours **narrow, typed, tool-mediated agents** over one large prompt.

**Target language:** JavaScript / Node.js. Every dataset entry is an npm package, and the QL code hints in the schemas are JS-flavoured.

---

## 3. Architecture: The Five-Stage Pipeline

```
data/<vic_name>/{before,after,diff.diff}
        │
        ▼
 ┌──────────────────────────────────────────────┐
 │ 1. identify-vuln-type-agent                  │  → VulnerabilityType
 │    "what class of bug did this commit add?"  │    {name, description}
 └──────────────────────────────────────────────┘
        │  vuln_type
        ▼
 ┌──────────────────────────────────────────────┐
 │ 2. source-sink-agent                         │  → SourceSinkAnalysis
 │    top-5 ranked source→sink pairs            │    {pairs[5]}
 └──────────────────────────────────────────────┘
        │  candidate endpoints
        ▼
 ┌──────────────────────────────────────────────┐
 │ 3. sanitizer-additionalFlowStep-agent        │  → FlowModelingAnalysis
 │    model flow gaps + sanitizers;             │    {additional_flow_steps,
 │    decide TaintTracking vs DataFlow          │     sanitizers,
 └──────────────────────────────────────────────┘     needs_taint_tracking,
        │  flow model                                 reasoning}
        ▼
 ┌──────────────────────────────────────────────┐
 │ 4. query-generate-agent   (CodeQL MCP tools) │  → QueryGeneration
 │    author, compile, format, validate a .ql   │    {status, query_path,
 └──────────────────────────────────────────────┘     explanation}
        │  query_path
        ▼
 ┌──────────────────────────────────────────────┐
 │ 5. execution-evaluation   (no LLM)           │  → bool pass/fail
 │    run on BOTH DBs → SARIF → signature diff  │    + summary + unique bugs
 │    pass iff vulnerable_count > fixed_count   │
 └──────────────────────────────────────────────┘
```

Stages 1–4 are LLM agents; stage 5 is deterministic. The `iteration_number` parameter threaded through stage 5 shows the intent is a **refinement loop** — generate, evaluate, feed the verdict back, regenerate — though the loop driver itself is not yet written.

### Stage detail

**1 — Identify vulnerability type** ([identify-vuln-type-agent.py](src/agent/identify-vuln-type-agent.py))
Classifies the bug class from before/after/diff. `thread_id "23456"`, response `VulnerabilityType`. Unlike its siblings it builds the agent inside `run()`, because the backend routes depend on `self.data_name`.

**2 — Source/sink identification** ([source-sink-agent.py](src/agent/source-sink-agent.py))
The most complete agent, and the pattern the others copy. Produces the top 5 most suspicious source→sink pairs, each with file, line, column, prose explanation and a risk `rank` (1 = riskiest). `thread_id "12345"`, response `SourceSinkAnalysis`. Writes a `.txt` dump of the structured response plus a JSON log of every tool call the agent made.

**3 — Sanitizer & additional-flow-step modeling** ([sanitizer-additionalFlowStep-agent.py](src/agent/sanitizer-additionalFlowStep-agent.py))
The most CodeQL-aware stage. It translates informal findings into QL building blocks: ordered `isAdditionalFlowStep` hops (typed `opaque_call`, `callback_param`, `property_read`, `return_capture`, `string_operation`), sanitizers (`value_sanitizer`, `guard_sanitizer`, `allowlist_check`) each with a confidence score, and the boolean `needs_taint_tracking` that decides `TaintTracking::Global` vs `DataFlow::Global`. `thread_id "34567"`, response `FlowModelingAnalysis`.

**4 — Query generation** ([query-generate-agent.py](src/agent/query-generator/query-generate-agent.py))
The only agent with external tools. It connects to the CodeQL MCP server, filters the tool list against an allowlist, and is asked to author a query — with compile/format/validate/LSP tools available so it can iterate on QL syntax before returning. Response `QueryGeneration`.

**5 — Execution & evaluation** ([execution-evaluation.py](src/agent/query-generator/execution-evaluation.py))
Two classes:

- `QueryExecution` runs three CodeQL CLI subprocesses per snapshot — `query run` → `.bqrs`, `bqrs interpret --format=sarif-latest` → `.sarif`, then `database cleanup --cache-cleanup=clear`. Artifacts are named `<data_name>_iteration_<n>_results.{bqrs,sarif}`.
- `Evaluation` extracts taint-path signatures from both SARIF files, computes `only_in_before` / `only_in_after` / `common`, applies the `vulnerable > fixed` criterion, and writes `unique_bugs_after_iteration_<n>.json` and `evaluation_summary_iteration_<n>.txt`.

Note the naming convention, documented in the summary output itself: **`before` = fixed, `after` = vulnerable**.

---

## 4. Key Technical Design Decisions

### 4.1 Virtual filesystem via `CompositeBackend`

Every agent mounts a `deepagents` `CompositeBackend` that routes virtual paths to different storage. From [source-sink-agent.py:34-50](src/agent/source-sink-agent.py#L34-L50):

```python
backend=CompositeBackend(
    default=StateBackend(),
    routes={
        "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
        "/vic/":      FilesystemBackend(root_dir=ROOT_DIR/"data"/self.data_name, virtual_mode=True),
        "/skills/":   FilesystemBackend(root_dir=ROOT_DIR/"skills"/"source-sink", virtual_mode=True),
    },
)
```

| Mount | Backs onto | Purpose |
| --- | --- | --- |
| `/vic/` | `data/<vic_name>/` | the code under analysis (read-only view) |
| `/skills/` | `skills/<agent>/` | the procedure the agent should follow |
| `/memories/` | LangGraph `InMemoryStore` | scratch notes across turns |
| *(default)* | agent state | ephemeral working files |

This is a **containment mechanism as much as a convenience**: the agent sees `/vic/` and cannot wander into the rest of the machine. `virtual_mode=True` keeps paths relative to the mount.

### 4.2 Pydantic-typed responses

Every agent passes `response_format=<Model>`, so the LLM must emit a validated object rather than prose. All models live in [structured_output.py](src/components/structured_output.py). This is what makes stage-to-stage handoff mechanical instead of parsing free text.

### 4.3 Skills as markdown

Procedure lives in `skills/<name>/SKILL.md` — YAML frontmatter plus numbered steps — not in the Python. Two are written:

**[skills/source-sink/SKILL.md](skills/source-sink/SKILL.md)** (189 lines, `name: extract-source-sink-pairs`) — the reference example. Five steps: comprehend changes → identify candidates → search code flows → score and rank → report top 5. Its "Traverse the Backend Precisely" section is notable for encoding *anti-hallucination* discipline: start from the diff, enumerate only paths the diff touched, expand one hop at a time, never guess filenames. Its budget constraints are equally deliberate — at most 2 `ls` calls total, no `..` traversal, files over 100 lines read in 100-line offset chunks, stop and report rather than invent when a file is unreadable. Ends with a full worked 5-entry JSON example.

**[skills/taint_path_tracking/SKILL.md](skills/taint_path_tracking/SKILL.md)** (82 lines, `name: extract-taint-paths`) — an alternative approach: annotate the code in place with `// tainted: "<var>"` comments and emit an interleaved prose+code report. Currently **orphaned** — no agent loads it, and it calls four tools (`fetch_folder_path`, `fetch_vulnerable_functions`, `insert_comment_at_line`, `extract_code_snippets`) that exist nowhere in the repo.

The remaining three (`identify-vuln-type`, `query-generate`, `sanitizer-additionalFlowStep`) are **0-byte `SKILLS.md`** — note the plural filename, which does not match the singular `SKILL.md` the written skills use.

### 4.4 CodeQL via MCP, with an allowlist

[mcp_client.py](src/components/mcp_client.py) spawns the vendored Node server over stdio:

```python
"codeql": {
    "transport": "stdio",
    "command": "node",
    "args": ["codeql-development-mcp-server/server/dist/codeql-development-mcp-server.js"],
    "env": {"CODEQL_CLI_PATH": CODEQL_CLI_PATH, "WORKSPACE_ROOT": ROOT_DIR_STR},
}
```

Running that module as `__main__` dumps every tool's name, description and schema to `mcp_tools.json` (69 KB at repo root) — a handy inventory of what the agent can reach.

The server exposes far more than the query author needs, so `ALLOWED_MCP_TOOLS_QUERY_GENERATE` in [config.py](src/config.py) narrows it to ~18 tools across four groups: database (`register_database`, `list_codeql_databases`, `read_database_source`), packs (`codeql_pack_ls`, `codeql_pack_install`, `codeql_resolve_library-path`), authoring (`create_codeql_query`, `validate_codeql_query`, `search_ql_code`, `codeql_query_compile`, `codeql_query_format`), and LSP (`codeql_lsp_diagnostics`, `codeql_lsp_completion`, `codeql_lsp_definition`, `codeql_lsp_references`, `codeql_lsp_document_symbols`). Scoping tools per-agent keeps the decision space small and the transcript readable.

### 4.5 Line-shift-resistant SARIF signatures

[compare_results.py](src/components/compare_results.py) is the subtle piece. Comparing two snapshots naively fails because the fix changed line numbers — identical findings would look different. So a taint path's signature deliberately **excludes line numbers and file URIs**:

```
(rule_id, source_start_col, source_end_col, source_text, sink_text, sink_start_col, sink_end_col)
```

Column offsets and the literal source/sink text survive line shifts, so set difference between the two SARIF files reflects real semantic differences rather than diff noise. Results with no `codeFlows` fall back to a 5-tuple `(rule_id, message, uri, startLine, startColumn)`.

### 4.6 LLM configuration

One factory, [get_llm.py](src/components/get_llm.py): `ChatGoogleGenerativeAI`, default `gemini-2.5-flash`, `temperature=0.5`, `convert_system_message_to_human=True`, key from `GOOGLE_API_KEY`. A fast/cheap model chosen over a stronger one — consistent with the design bet that **scaffolding and verification matter more than raw model strength**.

---

## 5. Repository Layout

```
deep_agent/
├── src/
│   ├── config.py                    ROOT_DIR, CODEQL_CLI_PATH, MCP tool allowlist
│   ├── main.py                      (empty — no unified entrypoint)
│   ├── utils.py                     setup_logger(), collect_tool_calls()
│   ├── agent/
│   │   ├── identify-vuln-type-agent.py            stage 1
│   │   ├── source-sink-agent.py                   stage 2
│   │   ├── sanitizer-additionalFlowStep-agent.py  stage 3
│   │   └── query-generator/
│   │       ├── query-generate-agent.py            stage 4
│   │       └── execution-evaluation.py            stage 5
│   └── components/
│       ├── get_llm.py               Gemini factory
│       ├── template.py              system prompts (only 1 of 3 present)
│       ├── structured_output.py     all Pydantic response schemas
│       ├── mcp_client.py            CodeQL MCP stdio client
│       └── compare_results.py       SARIF signature differ
├── skills/
│   ├── source-sink/SKILL.md                       189 lines ✔
│   ├── taint_path_tracking/SKILL.md               82 lines ✔ (orphaned)
│   ├── identify-vuln-type/SKILLS.md               0 bytes ✘
│   ├── query-generate/SKILLS.md                   0 bytes ✘
│   └── sanitizer-additionalFlowStep/SKILLS.md     0 bytes ✘
├── data/                            10 VIC fixtures (gitignored)
├── output/                          per-VIC agent results (gitignored)
├── old_output/                      earlier run archive (gitignored)
├── logs/                            deep_agent.log (gitignored)
├── scripts/
│   ├── run_agent_once.sh            single VIC
│   └── run_agent_at_scale.sh        batch over data/*/ with resume
├── codeql-development-mcp-server/   vendored third-party clone (untracked)
├── convert_to_json.py               repr(...) → JSON post-processor (gitignored)
├── mcp_tools.json                   dumped MCP tool inventory (69 KB)
├── Dockerfile / docker-compose.yml  ubuntu + venv at /opt/venv
├── requirements.txt                 deepagents, langchain-ollama, dotenv
├── .env                             GOOGLE_API_KEY, CODEQL_CLI_PATH (gitignored)
└── .mcp.json                        editor-side MCP config (gitignored)
```

### The dataset

`data/` holds **10 VIC fixtures**, all npm packages, each `before/` + `after/` + `diff.diff` containing only the files the commit touched:

`flat_5.0.0` · `html-parse-stringify_2.0.0` · `html-parse-stringify2_2.0.1` · `jsonpointer_4.0.0` · `nth-check_2.0.0` · `property-expr_2.0.2` · `safe-flat_2.0.0` · `static-eval_1.1.1` · `ua-parser-js_0.7.22` · `underscore_1.13.0-0`

These are recognisable real-world CVEs — prototype pollution (`flat`, `safe-flat`, `jsonpointer`, `property-expr`), ReDoS (`nth-check`, `ua-parser-js`), code injection (`static-eval`, `underscore`), and HTML-parsing bugs. Small, single-purpose packages with tight diffs: ideal for a pipeline that must read the whole change.

`output/` shows stage 2 has been run across all 10, each producing `<vic>_source_sink_analysis.txt`, `<vic>_tool_calls.json` and `parsed_source_sink_pairs.json`. The two 2.5–2.9 MB `CVE-2025-99999-query-iter-1_*_results.json` files at repo root are a stage-5 differential comparison captured from a synthetic test CVE.

`convert_to_json.py` is a pragmatic patch over stage 2: because the agent output was written with `str(structured_response)` — Python `repr` — it takes a balanced-parenthesis scanner and regexes to recover `SourceSinkPair(...)` objects back into JSON. Serialising with `.model_dump_json()` in the first place would make it unnecessary.

---

## 6. How to Run It

**Docker** (per [README.md](README.md)):

```bash
docker compose up -d --build
docker exec -it deep_agent /bin/bash
```

The image is `ubuntu:latest` with a venv at `/opt/venv` prepended to `PATH`; compose bind-mounts `.:/app` with `working_dir: /app`, `stdin_open` and `tty` — an interactive dev container, not a batch runner.

**Individual stages** (each file has its own `__main__`):

```bash
python src/agent/identify-vuln-type-agent.py            <vic_name> <vuln_type>
python src/agent/source-sink-agent.py                   <vic_name> <vuln_type>
python src/agent/sanitizer-additionalFlowStep-agent.py  <vic_name> <vuln_type>
python -m src.components.mcp_client                     # dump mcp_tools.json
python -m src.components.compare_results                # diff two SARIF files
```

**Batch:** [scripts/run_agent_at_scale.sh](scripts/run_agent_at_scale.sh) loops `data/*/`, derives each `vic_name`, skips VICs whose output already exists (resumable), and times each run plus the total via an HH:MM:SS helper. Both shell scripts currently invoke a module that no longer exists — see below.

Required environment (in `.env`): `GOOGLE_API_KEY` and `CODEQL_CLI_PATH`.

---

## 7. Design Themes Worth Noting

Several choices recur and are worth calling out as the repo's actual engineering opinions:

1. **Decomposition over one big prompt.** Classify → locate → model flow → author → verify. Each step has one job and a typed output, so a failure is attributable to a stage.
2. **Typed contracts between stages.** Pydantic everywhere; no prose parsing between agents.
3. **Deterministic ground truth.** The only pass/fail authority is the CodeQL CLI and a set difference. The LLM never grades itself.
4. **Least privilege for tools and files.** Per-agent MCP allowlists; per-agent virtual FS mounts.
5. **Explicit anti-hallucination discipline.** The source-sink skill bans guessing filenames, caps `ls` calls, forbids `..`, and requires citing only directly-read locations — bounding both cost and confabulation.
6. **Full auditability.** Every agent dumps its tool-call trace to JSON alongside its result, so a run can be reconstructed.
7. **Iteration built into the data model.** `iteration_number` is threaded through execution and evaluation artifacts; the refine loop is designed for even though it is not yet wired.

---

## 8. Current State & Known Gaps

This is an active prototype. Stage 2 works and has been run over the whole dataset; stages 4–5 are partly built. An honest inventory:

### Blocking

| Gap | Location |
| --- | --- |
| `IDENTIFY_VULN_TYPE_SYSTEM_PROMPT` and `SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT` are imported by stages 1 and 3 but **do not exist** — `template.py` defines only `SOURCE_SINK_SYSTEM_PROMPT`. Both agents fail at import. | [template.py](src/components/template.py) |
| `query-generate-agent.py` cannot run: `self.system_prompt` is never assigned (its import is commented out); `logger` is imported from `langgraph.store.memory`; `await self.agent.invoke(...)` should be `ainvoke`; the `except ImportError` fallback omits `create_mcp_client` and `QueryGeneration`; `main()` iterates the returned agent as if it were a tool list. | [query-generate-agent.py](src/agent/query-generator/query-generate-agent.py) |
| Both shell scripts call `python3 -m src.agent.deep_agent`, a module deleted in commit `3de1470`. Stale `deep_agent.cpython-31*.pyc` files remain under `src/agent/__pycache__/`. | [run_agent_once.sh](scripts/run_agent_once.sh), [run_agent_at_scale.sh](scripts/run_agent_at_scale.sh) |
| Three of five skills are **0-byte `SKILLS.md`** — and the filename is plural where the working skills use singular `SKILL.md`. | `skills/*/` |
| `requirements.txt` lists only `deepagents`, `langchain-ollama`, `dotenv`. Missing: `langchain-google-genai`, `langchain-mcp-adapters`, `langgraph`, `pydantic`. `langchain-ollama` is listed but imported nowhere. | [requirements.txt](requirements.txt) |

### Correctness bugs

| Bug | Location |
| --- | --- |
| **Missing comma** in the tool allowlist: `"codeql_resolve_packs"` and `"codeql_pack_ls"` concatenate into the single string `"codeql_resolve_packscodeql_pack_ls"`, so both tools are silently unavailable to the query author. | [config.py:13-14](src/config.py#L13-L14) |
| **Missing comma** in the CodeQL args list: `"-t" "kind=problem"` becomes `"-tkind=problem"`. | [execution-evaluation.py:94](src/agent/query-generator/execution-evaluation.py#L94) |
| `CODEQL_CLI_PATH='C:\Program Files\codeql'` is a non-raw string — `\P` and `\c` are not valid escapes and the path is fragile. (The runtime value comes from `.env`, so this constant is mainly a fallback.) | [config.py:7](src/config.py#L7) |
| `_signature_to_dict` handles only the 7-tuple taint-path signature and implicitly returns `None` for the 5-tuple fallback, so non-codeFlow findings become `null` entries in the diff JSON. `_signature_to_text` handles both. | [compare_results.py](src/components/compare_results.py) |

### Integration mismatches

| Mismatch | Detail |
| --- | --- |
| **Stage 2 → stage 3 handoff is broken.** Stage 3 mounts `data/<vic>/source-sink-agent_output/` (underscore, under `data/`), but stage 2 writes to `output/<vic>/source-sink-agent-output/` (hyphen, under `output/`). |
| **Result-key inconsistency.** Stages 1–2 read `result['structured_response']`; stage 3 reads `result['structured_output']`. |
| **Skill vs schema conflict.** `SKILL.md` documents `location{line_numbers: [int], code_snippet: string}` and `explanation`, and requires padding to exactly 5 entries with `null`. The schema defines `Location{line, column}` and `explaination` (misspelled), and `List[SourceSinkPair]` cannot hold `null`. The model is given two incompatible output specs. |
| **Two conflicting MCP configs.** `.mcp.json` points at `codeql-lsp-mcp/dist/index.js` (a path that does not exist); `mcp_client.py` points at `codeql-development-mcp-server/server/dist/…`. |
| **No orchestrator.** `src/main.py` is empty. Stages are run individually; nothing chains 1→2→3→4→5, and no loop feeds stage 5's verdict back into stage 4 despite the `iteration_number` plumbing. |
| **`taint_path_tracking` skill is orphaned** and depends on four tools that do not exist. |

### Cosmetic

- Agent filenames use hyphens (`source-sink-agent.py`), so they are not importable as modules — only runnable as scripts.
- `explaination` is misspelled throughout the schema, outputs, and `convert_to_json.py`.
- Vietnamese comments remain in `get_llm.py`, `compare_results.py`, and `run_agent_at_scale.sh`.
- `codeql-development-mcp-server/` is a vendored clone with its own `.git/`, committed as untracked files rather than a submodule or pinned dependency.

### Suggested order of work

1. Write the three missing system prompts in `template.py` (unblocks stages 1 and 3).
2. Fix the two missing commas (silent, high-impact).
3. Fill the three empty skill files and rename them `SKILL.md`.
4. Repair `query-generate-agent.py` (`ainvoke`, `system_prompt`, `logger`, import fallback).
5. Align the stage 2 → stage 3 output path and the `structured_response` / `structured_output` key.
6. Reconcile `SKILL.md`'s output format with the Pydantic schema — pick one.
7. Complete `requirements.txt`.
8. Write the orchestrator in `main.py`, including the generate → evaluate → refine loop.
9. Serialise agent output with `.model_dump_json()` and retire `convert_to_json.py`.
10. Delete the stale `__pycache__` fossils and update both shell scripts.

---

## 9. Summary

`deep_agent` is a **research pipeline for automated CodeQL query synthesis from vulnerability-inducing commits**. It decomposes an expert security task into four typed LLM stages — classify the bug, locate source/sink candidates, model the taint flow, author the query — and closes the loop with a deterministic CodeQL execution harness whose verdict is a differential one: the query must fire more on the vulnerable snapshot than on the fixed one.

The interesting engineering is in the scaffolding rather than the prompting: virtual filesystems that bound what each agent can see, Pydantic contracts that make handoffs mechanical, MCP tool allowlists scoped per agent, line-shift-resistant SARIF signatures that make the differential comparison meaningful, and skill files that encode explicit anti-hallucination discipline.

Stage 2 (source/sink identification) is complete and has produced results across all 10 dataset entries. Stages 1, 3 and 4 are scaffolded but blocked on missing prompts, empty skill files and a handful of bugs. Stage 5 — the evaluation harness — is the most finished code in the repo. The orchestration layer that would join them into the intended refinement loop has not been written yet.
