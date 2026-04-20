# Research Agent - Agent Guidelines

## Setup
1. Create Python 3.11+ venv: `python -m venv .venv`
2. Activate: `.\.venv\Scripts\Activate.ps1` (PowerShell)
3. Install deps: `pip install -e .[dev]` (includes test/dev dependencies)
4. Copy env: `copy .env.example .env`
5. Optional: Install Playwright for browser search: `pip install playwright && python -m playwright install chromium`

## Running the App
- Gradio UI (default): `python -m research_agent.app.gradio_app`
- FastAPI UI: `uvicorn research_agent.app.webapp:app --reload` (then visit http://127.0.0.1:8000)
- Bootstrap script: `.\scripts\bootstrap.ps1` (or `.\scripts\bootstrap.ps1 -Dev` for dev deps)

## Testing
- Run all tests: `pytest`
- Run with coverage: `pytest --cov=src`
- Test single file: `pytest tests/test_specific.py`
- Smoke test: `pytest tests/unit/test_smoke.py`

## Code Quality
- Lint: `ruff check src`
- Format: `ruff check --fix src`
- Typecheck: `mypy src`

## Key Directories
- `src/research_agent/`: Main application source
- `tests/`: Unit, integration, and end-to-end tests
- `artifacts/`: Generated output (`main.tex`, `references.bib`, etc.)
- `data/`: Local research artifacts (graph, processed, raw, vector_index)
- `configs/`: Runtime configuration templates
- `scripts/`: Helper scripts (bootstrap.ps1)

## Environment Variables (in .env)
- Web retrieval: `WEB_PROVIDER=scrape|duckduckgo|browser_use|hybrid`
- Paper sources: `PAPER_PROVIDERS=arxiv,semantic_scholar,openalex`
- Browser Use: `BROWSER_USE_API_KEY=...` (optional)
- NVIDIA model: `ENABLE_NVIDIA_MODEL=true` + `NVIDIA_API_KEY=...` + `NVIDIA_MODEL=...`
- Runtime controls: `MAX_ITERATIONS=4`, `MAX_RUNTIME_MINUTES=25`, `MAX_COST_USD=5.0`, `DEFAULT_TEMPLATE=ieee`

## Notes
- Deterministic fallback: If NVIDIA API unavailable, composer uses local deterministic mode.
- Deep RAG: Uses in-memory Qdrant for evidence retrieval.
- Critic loops: Up to 3 iterative research cycles for low-confidence sections.
- Artifacts: Exported to `artifacts/<run_id>/` as `main.tex`, `references.bib`, `compile_instructions.md`, `summary.json`.
- Entry points: `research_agent.app.gradio_app` (Gradio), `research_agent.app.webapp:app` (FastAPI)
- Test pattern: Tests follow `test_*.py` naming, located in `tests/unit/` and `tests/integration/`