# Automaton Auditor - Digital Courtroom

A hierarchical LangGraph agent swarm for autonomous code audit. Implements the "Digital Courtroom" architecture: Detective agents collect forensic evidence, Judge personas (Prosecutor, Defense, Tech Lead) deliberate in parallel, and a Chief Justice synthesizes the final verdict.

## Architecture

```
START → [RepoInvestigator || DocAnalyst || VisionInspector] (fan-out)
     → EvidenceAggregator (fan-in)
     → [Prosecutor || Defense || TechLead] (fan-out)
     → ChiefJustice (fan-in)
     → END
```

- **Detectives:** Clone repo, parse AST, extract git history, ingest PDF, analyze diagrams
- **Judges:** Distinct personas evaluate evidence per rubric criterion; structured output via Pydantic
- **Chief Justice:** Hardcoded deterministic conflict resolution (security override, fact supremacy, dissent)

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Installation

```bash
# With uv
uv sync

# Or with pip
pip install -e .
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required:
- `GOOGLE_API_KEY` – for Gemini (get free key at https://aistudio.google.com/apikey)

Optional:
- `LANGCHAIN_TRACING_V2=true` – enable LangSmith tracing
- `LANGCHAIN_PROJECT=automaton-auditor`
- `AUDITOR_LLM_MODEL=gemini-1.5-flash` (default, free tier)

## Usage

### Run Audit

```python
from src.graph import run_audit
from src.nodes.justice import report_to_markdown

result = run_audit(
    repo_url="https://github.com/owner/week2-repo",
    pdf_path="/path/to/architectural_report.pdf"
)

report = result.get("final_report")
if report:
    md = report_to_markdown(report)
    with open("audit/report.md", "w") as f:
        f.write(md)
```

### CLI (optional)

```bash
python -m src.main "https://github.com/owner/repo" /path/to/report.pdf
```

## Project Structure

```
src/
├── state.py          # Pydantic/TypedDict state (Evidence, JudicialOpinion, AgentState)
├── graph.py          # StateGraph wiring
├── tools/
│   ├── repo_tools.py # git clone, git log, AST analysis (sandboxed)
│   └── doc_tools.py  # PDF ingestion, image extraction
├── nodes/
│   ├── detectives.py # RepoInvestigator, DocAnalyst, VisionInspector
│   ├── judges.py     # Prosecutor, Defense, TechLead (.with_structured_output)
│   └── justice.py    # ChiefJusticeNode, report_to_markdown
└── main.py           # CLI entry point
rubric.json           # Machine-readable scoring rubric
```

## Rubric

The agent evaluates against `rubric.json` (10 dimensions):

- Git Forensic Analysis, State Management Rigor, Graph Orchestration
- Safe Tool Engineering, Structured Output, Judicial Nuance
- Chief Justice Synthesis, Theoretical Depth, Report Accuracy
- Architectural Diagram Analysis

## License

MIT
