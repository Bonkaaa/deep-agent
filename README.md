# Deep Agent

`deep_agent` is an AI-powered security analysis agent designed for automated taint path tracking and vulnerability discovery. Built using [DeepAgents](https://github.com/langchain-ai/deepagents), [LangChain](https://github.com/langchain-ai/langchain), and [LangGraph](https://github.com/langchain-ai/langgraph), it analyzes target codebases to identify and document propagation paths from untrusted data sources to vulnerable sinks.

---

## Features

- **Automated Taint Path Tracking**: Systematically traces data flows and function call sequences from sources to sinks.
- **Custom Agent Tools**:
  - `fetch_folder_path`: Resolves the target codebase path from runtime context.
  - `fetch_vulnerable_functions`: Identifies known vulnerable sinks to analyze.
  - `extract_code_snippets`: Reads and extracts specific line ranges for in-depth analysis.
  - `insert_comment_at_line`: Annotates source code files with taint propagation notes (`// taint: ...`).
- **Skill-Driven Agent Architecture**: Leverages structured skill definitions (`skills/taint_path_tracking/SKILL.md`) stored in an in-memory store for consistent analytical reasoning.
- **Ollama LLM Integration**: Uses local LLMs (e.g., `gpt-oss:20b`) via `langchain-ollama`.
- **Containerized Environment**: Pre-configured Docker and Docker Compose setup for isolated and reproducible execution.

---

## Project Structure

```text
deep_agent/
├── data/                       # Vulnerability datasets & target codebases for analysis
├── scripts/
│   └── run_agent.sh            # Script to execute the deep agent runner
├── skills/
│   └── taint_path_tracking/    # Agent skills and analysis guidelines (SKILL.md)
├── src/
│   ├── agent/
│   │   └── deep_agent.py       # Core Deep Agent definition, tools, and execution flow
│   └── components/
│       ├── get_llm.py          # LLM client initialization (Ollama)
│       └── template.py         # System prompt templates
├── Dockerfile                  # Container definition with Python venv
├── docker-compose.yml          # Compose specification for container orchestration
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## Prerequisites

- **Docker & Docker Compose** (recommended)
- **Ollama** running locally or accessible on your network with the target model pulled (e.g., `ollama pull gpt-oss:20b`)
- *(Optional for local runs)* **Python 3.10+**

---

## Getting Started

### Using Docker (Recommended)

1. **Build and start the container in the background:**
   ```bash
   docker compose up -d --build
   ```

2. **Access the container shell:**
   ```bash
   docker exec -it deep_agent /bin/bash
   ```

3. **Run the agent:**
   ```bash
   python3 -m src.agent.deep_agent
   ```
   *Alternatively, run the helper script:*
   ```bash
   ./scripts/run_agent.sh
   ```

4. **Stop the container:**
   ```bash
   docker compose down
   ```

---

### Local Setup (Without Docker)

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the agent:**
   ```bash
   python -m src.agent.deep_agent
   ```

---

## Output

Analysis results and final vulnerability reports are saved to the `output/` directory (e.g., `output/taint_path_report.txt`).