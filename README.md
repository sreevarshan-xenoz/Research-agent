# Research Agent

API-first, subagent-driven research system that performs iterative topic research and exports grounded LaTeX source packages.

Current implementation is a working v1 pipeline with:
- Clarification-first intake for ambiguous topics
- Dependency-aware multi-pass worker execution
- Critic scoring and section synthesis
- Citation extraction and verification pass
- LaTeX package generation and artifact export

## v1 Scope
- Works without paid APIs by default
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
3. Copy `.env.example` to `.env`.
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

## Free-First Retrieval
The default setup uses free web retrieval and local composition.

Set in `.env`:

- `WEB_PROVIDER=scrape` for free DuckDuckGo HTML scraping
- `WEB_PROVIDER=duckduckgo` for free DuckDuckGo package-backed search
- `WEB_PROVIDER=browser_use` for browser-first mode
- `WEB_PROVIDER=hybrid` to run both browser use and DuckDuckGo in worker searches
- `PAPER_PROVIDERS=arxiv,semantic_scholar,openalex` for free paper metadata search
- `BROWSER_USE_API_KEY=...` to use official Browser Use hosted model path (`ChatBrowserUse`)
- optional `BROWSER_USE_MODEL=bu-2-0`
- optional `BROWSER_USE_OPENAI_MODEL=...` when using OpenAI/OpenRouter-backed `ChatOpenAI`

Optional browser runtime setup:

```powershell
pip install playwright
python -m playwright install chromium
```

If Playwright is unavailable or browser search fails, the adapter automatically uses HTTP scraping fallback.
Adapter fallback order is: browser-use SDK -> Playwright -> HTTP scraping.

## Optional Hosted Model Usage
By default, the composer stays local/deterministic. To enable NVIDIA generation in the composer stage, set these in `.env`:

- `ENABLE_NVIDIA_MODEL=true`
- `NVIDIA_API_KEY=...` (or `NVIDIA_NIMS_API_KEY=...`)
- `NVIDIA_MODEL=qwen/qwen3-coder-480b-a35b-instruct`

The integration uses `ChatNVIDIA(...).stream(...)` and falls back to deterministic local composition if the NVIDIA call is unavailable.

## Notes
- The worker/planner/critic flow is hybrid: it uses LLM-driven dynamic planning and clarification when `NVIDIA_API_KEY` is available, with robust deterministic fallbacks.
- Deep RAG is implemented using an in-memory Qdrant index, providing semantic evidence retrieval for section synthesis.
- The Critic agent can trigger up to 3 iterative research loops to address low-confidence findings.
- Final deliverables are source artifacts (`main.tex`, `references.bib`) and optional compile instructions.

## End-to-End Flow (v1)
1. **Intake:** Ambiguity detection and topic normalization.
2. **Clarification:** Dynamic LLM-generated questions (if needed).
3. **Planning:** Dynamic subtopic graph creation with dependency mapping.
4. **Worker Execution:** Multi-pass parallel and gated task execution.
5. **Indexing:** Deep RAG evidence ingestion (Chunking + Vector Indexing).
6. **Critic Scoring:** Confidence evaluation and dynamic follow-up task generation.
7. **Iteration:** (Optional) Loop back to workers for targeted evidence recovery.
8. **Synthesis:** Combiner produces section drafts using RAG-retrieved evidence.
9. **Verification:** Citation verifier extracts and validates source records.
10. **Composition:** Composer generates `main.tex` and `references.bib`.
11. **Export:** Exporter writes artifact package to `artifacts/<run_id>/`.

## Exported Artifacts
Each completed run writes:
- `main.tex`
- `references.bib`
- `compile_instructions.md`
- `summary.json`
