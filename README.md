# Research Agent

API-first, subagent-driven research system that performs iterative topic research and exports grounded LaTeX source packages.

Current implementation is a working v1 pipeline with:
- Clarification-first intake for ambiguous topics
- Dependency-aware multi-pass worker execution
- Critic scoring and section synthesis
- Citation extraction and verification pass
- LaTeX package generation and artifact export

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

## Web App (LLM-Style UI)
Run the browser-based chat experience:

```powershell
uvicorn research_agent.app.webapp:app --reload
```

Then open `http://127.0.0.1:8000`.

## Notes
- Local model support is intentionally deferred to v2.
- Final deliverables are source artifacts (`main.tex`, `references.bib`) and optional compile instructions.

## End-to-End Flow (v1)
1. Intake and ambiguity detection
2. Clarification questions (if needed)
3. Planner builds dependent subtopic tasks
4. Worker executes tools until all dependencies resolve or block
5. Critic scores evidence confidence
6. Combiner produces section drafts
7. Citation verifier extracts citation records
8. Composer generates `main.tex` and `references.bib`
9. Exporter writes artifact package to `artifacts/<run_id>/`

## Exported Artifacts
Each completed run writes:
- `main.tex`
- `references.bib`
- `compile_instructions.md`
- `summary.json`
