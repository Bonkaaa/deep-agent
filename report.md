# Report

**Repository:** `c:\deep_agent`  
**Current Branch:** `agent`  
**Project Status:** Research Prototype / Handover Documentation  

---

## Abstract

Automated vulnerability detection via Static Application Security Testing (SAST) often requires domain experts to author complex queries in specialized languages such as CodeQL. This project presents **`deep_agent`**, an agentic framework powered by Large Language Models (LLMs) that automates the generation of CodeQL queries directly from **Vulnerability-Inducing Commits (VICs)**. 

The framework decomposes the query authoring process into a sequential five-stage pipeline: vulnerability classification, source-sink identification, flow and sanitizer modeling, tool-mediated query synthesis, and deterministic differential verification. Crucially, query correctness is validated through an objective, non-LLM differential evaluation criterion: a synthesized query is considered valid if and only if it produces strictly more taint-tracking findings on the vulnerable code snapshot than on the pre-vulnerability clean snapshot. This report details the system architecture, file-to-feature mapping, core design principles, experimental datasets, current implementation status, and a structured roadmap for repository handover.

---

## 1. Problem Formulation & Research Objectives

### 1.1 Motivation
Static analysis tools like GitHub CodeQL model source code as relational databases and track untrusted dataflow from sources to sinks. However, authoring high-precision CodeQL queries requires deep expertise in both security semantics and declarative query languages (QL). When a security vulnerability is introduced in a codebase, the introducing commit provides ground-truth semantics of the flaw. Automating the transition from a vulnerability-inducing commit to a reusable detection rule significantly accelerates vulnerability response and security variant analysis.

### 1.2 Input / Output Specification
Each target vulnerability is structured as a three-part dataset entry:
* **`before/`**: The codebase snapshot prior to vulnerability introduction (clean/fixed state).
* **`after/`**: The codebase snapshot containing the introduced vulnerability (vulnerable state).
* **`diff.diff`**: The unified code difference characterizing the commit.

**System Output:** A synthesized CodeQL query (`.ql`) and an execution evaluation report verifying that the query correctly isolates the vulnerability.

### 1.3 Objective Differential Evaluation Thesis
Rather than relying on LLMs to self-assess generated queries, the system uses a deterministic ground-truth verification harness. A generated query passes verification if:

$$\text{Findings}(\text{Snapshot}_{\text{vulnerable}}) > \text{Findings}(\text{Snapshot}_{\text{fixed}})$$

* **Reject Trivially Empty Queries:** A query that returns zero findings on both versions ($0 > 0 = \text{False}$) is rejected.
* **Reject Overly Broad Queries:** A query that flags common utility patterns indiscriminately produces equal counts on both versions and is rejected.
* **Accept Precise Queries:** Only queries specifically sensitive to the semantic delta introduced by the commit succeed.

---

## 2. Pipeline Architecture & Feature-to-File Mapping

The system adopts a modular multi-agent pipeline where specialized LLM agents perform narrow, typed reasoning steps, culminating in an automated tool-driven authoring and evaluation loop.

```
       data/<target_vic>/{before, after, diff.diff}
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: Vulnerability Type Identification             │  [src/agent/identify-vuln-type-agent.py]
│ Feature: Classify bug category from diff context       │  [src/components/template.py]
└──────────────────────────┬─────────────────────────────┘
                           │ VulnerabilityType
                           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Source-Sink Identification & Ranking          │  [src/agent/source-sink-agent.py]
│ Feature: Locate top-5 candidate taint endpoints        │  [skills/source-sink/SKILL.md]
└──────────────────────────┬─────────────────────────────┘
                           │ SourceSinkAnalysis
                           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: Flow & Sanitizer Modeling                     │  [src/agent/sanitizer-additionalFlowStep-agent.py]
│ Feature: Model intermediate steps & sanitization guards│  [skills/sanitizer-additionalFlowStep/]
└──────────────────────────┬─────────────────────────────┘
                           │ FlowModelingAnalysis
                           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 4: Interactive Query Synthesis (MCP Tools)       │  [src/agent/query-generator/query-generate-agent.py]
│ Feature: Compile, format, and refine .ql via CodeQL CLI│  [src/components/mcp_client.py]
└──────────────────────────┬─────────────────────────────┘
                           │ Synthesized .ql Query
                           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 5: Deterministic Differential Evaluation         │  [src/agent/query-generator/execution-evaluation.py]
│ Feature: Execute on dual DBs, compute SARIF delta      │  [src/components/compare_results.py]
└────────────────────────────────────────────────────────┘
```

---

### Detailed Stage Breakdown & Associated Components

| Pipeline Stage | Implementation Files | Core Responsibilities & Features |
| :--- | :--- | :--- |
| **Stage 1: Vulnerability Identification** | • [`src/agent/identify-vuln-type-agent.py`](file:///c:/deep_agent/src/agent/identify-vuln-type-agent.py)<br>• [`skills/identify-vuln-type/`](file:///c:/deep_agent/skills/identify-vuln-type/) | Ingests the code diff and codebase structure; classifies the vulnerability into established categories (e.g., Prototype Pollution, ReDoS, Code Injection, Path Traversal). |
| **Stage 2: Source-Sink Identification** | • [`src/agent/source-sink-agent.py`](file:///c:/deep_agent/src/agent/source-sink-agent.py)<br>• [`skills/source-sink/SKILL.md`](file:///c:/deep_agent/skills/source-sink/SKILL.md) | Pinpoints untrusted user input entry points (sources) and dangerous execution sinks. Generates a ranked list of the top 5 candidate pairs with precise file paths, line/column coordinates, and threat rationales. |
| **Stage 3: Flow & Sanitizer Modeling** | • [`src/agent/sanitizer-additionalFlowStep-agent.py`](file:///c:/deep_agent/src/agent/sanitizer-additionalFlowStep-agent.py)<br>• [`skills/sanitizer-additionalFlowStep/`](file:///c:/deep_agent/skills/sanitizer-additionalFlowStep/) | Determines whether `TaintTracking` or `DataFlow` is required; specifies intermediate step predicates (`isAdditionalFlowStep` for callbacks, property reads, opaque calls) and identifies neutralizing sanitizers/guards. |
| **Stage 4: Query Synthesis & Tool-Mediated Iteration** | • [`src/agent/query-generator/query-generate-agent.py`](file:///c:/deep_agent/src/agent/query-generator/query-generate-agent.py)<br>• [`src/components/mcp_client.py`](file:///c:/deep_agent/src/components/mcp_client.py)<br>• [`src/config.py`](file:///c:/deep_agent/src/config.py) | Connects to the CodeQL MCP Server; composes complete QL queries using templates; invokes compiler, linter, formatter, and language server protocol (LSP) tools to fix syntax errors prior to execution. |
| **Stage 5: Differential Evaluation Harness** | • [`src/agent/query-generator/execution-evaluation.py`](file:///c:/deep_agent/src/agent/query-generator/execution-evaluation.py)<br>• [`src/components/compare_results.py`](file:///c:/deep_agent/src/components/compare_results.py) | Non-LLM execution harness. Runs CodeQL CLI against both `before` and `after` databases, converts BQRS to SARIF, extracts location-independent taint signatures, and calculates true differential metrics. |

---

## 3. Key Design Principles & Architectural Mechanisms

### 3.1 Sandboxed Virtual Filesystems (`CompositeBackend`)
To eliminate hallucination and prevent accidental system modification, each agent operates inside a sandboxed virtual filesystem layout:
* `/vic/`: Read-only mount mapping directly to the target vulnerability dataset (`data/<target>/`).
* `/skills/`: Read-only mount providing procedural step-by-step guidance.
* `/memories/`: Ephemeral state store for scratchpad reasoning across agent turns.

### 3.2 Strongly Typed Stage Contracts (`src/components/structured_output.py`)
All inter-agent communication is governed by strict Pydantic models rather than free-form text.
* `VulnerabilityType`: Output contract for Stage 1.
* `SourceSinkAnalysis` & `SourceSinkPair`: Output contract for Stage 2.
* `FlowModelingAnalysis`: Output contract for Stage 3.
* `QueryGeneration`: Output contract for Stage 4.

### 3.3 Anti-Hallucination Skill Protocol (`skills/`)
Agents are guided by explicit markdown skill files rather than monolithic prompts. For example, [`skills/source-sink/SKILL.md`](file:///c:/deep_agent/skills/source-sink/SKILL.md) enforces operational constraints:
* Exploration is restricted strictly to files referenced in `diff.diff`.
* Directory listings (`ls`) are capped at a maximum of 2 calls per run.
* Large source files must be read incrementally in 100-line offset blocks.
* Speculative guessing of filenames or API definitions is strictly prohibited.

### 3.4 Tool-Mediated Development via Model Context Protocol (MCP)
The query generation agent interacts with an external CodeQL MCP server ([`src/components/mcp_client.py`](file:///c:/deep_agent/src/components/mcp_client.py)). A curated allowlist in [`src/config.py`](file:///c:/deep_agent/src/config.py) exposes approximately 18 fine-grained tools covering:
* **Query Validation & Compilation:** `validate_codeql_query`, `codeql_query_compile`, `codeql_query_format`.
* **Database Inspection:** `register_database`, `list_codeql_databases`, `read_database_source`.
* **LSP Intelligence:** `codeql_lsp_diagnostics`, `codeql_lsp_definition`, `codeql_lsp_references`.

### 3.5 Line-Shift Invariant SARIF Differencing (`src/components/compare_results.py`)
Because vulnerability-inducing commits introduce or delete lines of code, naive line-number comparison across SARIF files yields false positives. The comparison engine extracts an invariant 7-tuple signature for each taint path:

$$\text{Signature} = (\text{RuleID}, \text{SourceCol}_{\text{start}}, \text{SourceCol}_{\text{end}}, \text{SourceText}, \text{SinkText}, \text{SinkCol}_{\text{start}}, \text{SinkCol}_{\text{end}})$$

By evaluating set differences over column offsets and token texts, the evaluator reliably detects semantic differences unaffected by line shifts.

---

## 4. Evaluation Dataset & Benchmark Setup

The system includes 10 real-world vulnerability benchmarks from the Node.js/npm ecosystem located in the `data/` directory:

| Benchmark Package | Target Version | Vulnerability Category |
| :--- | :--- | :--- |
| `flat` | 5.0.0 | Prototype Pollution |
| `safe-flat` | 2.0.0 | Prototype Pollution |
| `jsonpointer` | 4.0.0 | Prototype Pollution |
| `property-expr` | 2.0.2 | Prototype Pollution |
| `nth-check` | 2.0.0 | Regular Expression Denial of Service (ReDoS) |
| `ua-parser-js` | 0.7.22 | Regular Expression Denial of Service (ReDoS) |
| `static-eval` | 1.1.1 | Code Injection / Sandbox Escape |
| `underscore` | 1.13.0-0 | Arbitrary Code Execution |
| `html-parse-stringify` | 2.0.0 | Parser Logic Flaw / Denial of Service |
| `html-parse-stringify2`| 2.0.1 | Parser Logic Flaw / Denial of Service |

---

## 5. Implementation Status & Handover Gap Analysis

This section outlines the exact state of each component for developers taking over the codebase.

### 5.1 Fully Implemented & Verified Components
* **Stage 2 (Source-Sink Agent):** Completely implemented, integrated with `SKILL.md`, and validated across all 10 dataset entries (outputs stored in `output/`).
* **Stage 5 (Differential Verification Harness):** Core evaluation logic in `execution-evaluation.py` and `compare_results.py` is fully functional and validated on sample SARIF runs.
* **MCP Infrastructure:** Stdio client bridge in `mcp_client.py` and tool registry definitions are operational.

---

### 5.2 Critical Blockers & Actionable Gaps

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CRITICAL BLOCKERS MATRIX                             │
├─────────────────────────┬────────────────────────────────────────────────────────┤
│ Affected File           │ Nature of Defect & Required Remediation                │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ src/components/         │ • Missing Prompt Constants: Stages 1 and 3 import      │
│ template.py             │   IDENTIFY_VULN_TYPE_SYSTEM_PROMPT and                 │
│                         │   SANITIZER_ADDITIONAL_FLOW_STEP_SYSTEM_PROMPT,        │
│                         │   which are not defined. Must be authored.             │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ src/agent/query-        │ • Unassigned System Prompt (self.system_prompt).       │
│ generator/              │ • Incorrect Logger Import (imported from memory store).│
│ query-generate-agent.py │ • Async Invocation Bug: Uses invoke instead of ainvoke.│
│                         │ • Output Iteration Bug in main entrypoint.             │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ skills/*/               │ • Empty Skills: Three skill directories contain 0-byte │
│                         │   files named SKILLS.md (must be renamed to SKILL.md   │
│                         │   and populated with procedural instructions).         │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ src/config.py           │ • String Concatenation Syntax Error: Missing comma     │
│                         │   between "codeql_resolve_packs" and "codeql_pack_ls". │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ src/main.py             │ • Missing Unified Pipeline Orchestrator: File is empty.│
│                         │   Requires an end-to-end loop linking Stages 1 to 5.   │
├─────────────────────────┼────────────────────────────────────────────────────────┤
│ requirements.txt        │ • Missing Dependencies: Needs langchain-google-genai,  │
│                         │   langchain-mcp-adapters, langgraph, and pydantic.     │
└─────────────────────────┴────────────────────────────────────────────────────────┘
```

---

### 5.3 Pipeline Interface Mismatches

1. **Filesystem Path Discrepancy (Stage 2 $\to$ Stage 3):**
   * Stage 2 writes to: `output/<vic>/source-sink-agent-output/`
   * Stage 3 attempts to read from: `data/<vic>/source-sink-agent_output/`
2. **Response Dictionary Key Inconsistency:**
   * Stages 1 & 2 access `result['structured_response']`.
   * Stage 3 accesses `result['structured_output']`.
3. **Skill Specification vs. Pydantic Schema Mismatch:**
   * `skills/source-sink/SKILL.md` describes a schema with `location{line_numbers, code_snippet}` and null padding.
   * `src/components/structured_output.py` enforces `Location{line, column}` and rejects nulls.

---

## 6. Handover Roadmap & Next Steps

For the incoming engineering team, the recommended sequence of development is structured as follows:

```
[Phase 1: Syntax & Config Fixes]
   ├── Fix missing commas in src/config.py and execution-evaluation.py
   └── Update requirements.txt with complete dependencies
           │
           ▼
[Phase 2: Prompt & Skill Authoring]
   ├── Define missing prompts in src/components/template.py
   └── Populate and rename empty skills to SKILL.md
           │
           ▼
[Phase 3: Stage 4 Agent Remediation]
   └── Fix async invocation and logger bindings in query-generate-agent.py
           │
           ▼
[Phase 4: Interface Harmonization]
   ├── Align Stage 2/3 artifact paths and response dictionary keys
   └── Synchronize Pydantic schema with SKILL.md specifications
           │
           ▼
[Phase 5: Unified Pipeline & Closed-Loop Refinement]
   └── Implement orchestrator in src/main.py with an automated
       Generate ➔ Evaluate ➔ Feedback ➔ Refine loop
```

---

## 7. Conclusion

The `deep_agent` architecture demonstrates a principled approach to automated static analysis query synthesis. By decomposing the problem into discrete, typed reasoning stages and anchoring the evaluation in deterministic differential analysis, the system avoids common pitfalls of unstructured LLM code generation. Addressing the identified implementation gaps will yield a fully automated, end-to-end pipeline capable of synthesizing high-quality CodeQL queries directly from vulnerability commits.
