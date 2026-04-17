# Research Agent

API-first, subagent-driven research system that performs iterative topic research and exports grounded LaTeX source packages.

## v1 Scope
- API model providers only
- Hybrid autonomy with clarification + critic loops
- Dependency-aware subagent orchestration
- Deep RAG evidence grounding
- LaTeX output: IEEE and ACM

## Repository Layout
- `spec/`: requirements, design, and delivery plan
- `src/research_agent/`: application source code
- `tests/`: unit, integration, and end-to-end tests
- `configs/`: runtime configuration templates
- `scripts/`: helper scripts
- `data/`: local research artifacts for development
- `artifacts/`: generated output artifacts

## Quick Start
1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` and set API keys.
4. Launch the web app entrypoint.

## Initial Commands
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy .env.example .env
python -m research_agent.app.gradio_app
```

## Notes
- Local model support is intentionally deferred to v2.
- Final deliverables are source artifacts (`main.tex`, `references.bib`) and optional compile instructions.
