# Research Agent - Agent Guidelines

## Project Overview
A LangGraph-based research agent that performs iterative topic research and exports grounded LaTeX papers. Uses a dependency-aware multi-pass worker execution with critic scoring, Deep RAG evidence grounding, and citation verification.

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy .env.example .env
```

## Running the App
| Command | Description |
|---------|-------------|
| `python -m research_agent.app.gradio_app` | Gradio UI (default) |
| `uvicorn research_agent.app.webapp:app --reload` | FastAPI UI (http://127.0.0.1:8000) |
| `.\scripts\bootstrap.ps1` | Bootstrap with dependencies |
| `.\scripts\bootstrap.ps1 -Dev` | Bootstrap with dev dependencies |

## Testing
| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest --cov=src` | Run with coverage |
| `pytest tests/unit/test_smoke.py` | Smoke test |
| `pytest tests/integration/` | Integration tests |

## Code Quality
| Command | Description |
|---------|-------------|
| `ruff check src` | Lint |
| `ruff check --fix src` | Lint + auto-fix |
| `mypy src` | Typecheck |

---

## Architecture

### LangGraph Workflow (`orchestration/graph.py`)
The core is a `StateGraph` with these nodes:
```
intake → clarifier → planner → worker_executor → indexing → critic → [replan?] → combiner
  ↓                                                        ↓
await_user                                              END
```

**Key routing logic:**
- `_route_after_clarifier`: Routes to `await_user` or `planner` based on `needs_clarification`
- `_route_after_worker`: Routes to `complete`, `loop`, or `stopped` based on task dependencies
- `_route_after_critic`: Routes to `replan`, `await_user_critic`, `combiner`, or `stopped`

**Stop reasons**: `user_interrupt`, `runtime_cap_reached`, `cost_cap_reached`, `max_iterations_reached`, `dependency_deadlock`

### State Management (`orchestration/state.py`)
- `GraphState` (TypedDict): LangGraph internal state
- `WorkflowState` (dataclass): External API/state conversion
- Converters: `to_graph_state()`, `from_graph_state()`

### Graph Node Pattern
Nodes are wrapped with `wrap_node_fn()` for observability:
```python
graph.add_node("worker_executor", wrap_node_fn("worker_executor", make_worker_node(tool_registry)))
```

### Checkpointing
- **MemorySaver**: Shared module-level (`_memory_checkpointer`) for local development
- **AsyncRedisSaver**: When `settings.features.session_persistence == "redis"`
- Interactive checkpoints pause at `plan_validation` when `runtime.interactive_checkpoints = true`

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/research_agent/orchestration/` | LangGraph workflow, nodes, state |
| `src/research_agent/orchestration/nodes/` | Individual graph node implementations |
| `src/research_agent/tools/` | Search/data retrieval adapters (arxiv, web, etc.) |
| `src/research_agent/models/` | LLM client abstractions |
| `src/research_agent/output/` | LaTeX generation, exporters, templates |
| `src/research_agent/observability/` | Logging, metrics, tracing |
| `src/research_agent/rag/` | Deep RAG (chunker, indexer) |
| `src/research_agent/app/` | Web UI entrypoints (Gradio, FastAPI) |
| `tests/unit/` | Unit tests with mocked LLM calls |
| `tests/integration/` | Integration tests |
| `artifacts/` | Generated output (main.tex, references.bib, summary.json) |
| `data/` | Local storage (graph, processed, raw, vector_index) |
| `configs/` | Runtime configuration templates |

---

## Configuration (`config/schema.py`)

Settings loaded via `load_settings()` from `configs/settings.yaml` or `.env`.

**Key settings:**
- `runtime.max_iterations`: Max critic loops (default 4)
- `runtime.max_runtime_minutes`: Timeout (default 25)
- `runtime.parallel_workers`: Max concurrent subagents (default 4)
- `retrieval.web_provider`: `scrape|duckduckgo|browser_use|hybrid`
- `retrieval.paper_providers`: `arxiv,semantic_scholar,openalex,pubmed`
- `features.session_persistence`: `localStorage|redis|none`

**Environment variable overrides**: Most settings can be set via `ENV_VAR` (checked via Pydantic validators).

---

## Tool Adapter Pattern (`tools/base.py`)

```python
class BaseToolAdapter(ABC):
    provider_name: str
    is_searcher: bool = True
    
    @abstractmethod
    def search(self, query: str, limit: int = 5) -> ToolResult: ...
    
    async def asearch(self, query: str, limit: int = 5) -> ToolResult:  # default impl
```

Tool registry built via `build_tool_registry(settings)` in `tools/registry.py`.

---

## Observability (`observability/`)

**Components:**
- `logging.py`: Structured logging with `log_error()`, `log_exception()`, `NodeTimer`
- `metrics.py`: Prometheus metrics (run duration, node timing, errors)
- `tracing.py`: OpenTelemetry tracing
- `structured_log.py`: Correlation IDs via contextvars

**Node timing**: All nodes automatically timed via `wrap_node_fn()` which records to Prometheus histograms.

---

## Gotchas and Non-Obvious Patterns

### Global State
- `_redis_pool`: Module-level Redis connection pool (shared across runs)
- `_memory_checkpointer`: Module-level MemorySaver for checkpoint resume
- `_INDEX_CACHE`, `_CONTRADICTION_CACHE`: In `orchestration/nodes/indexing.py`

### Test Patterns
- `conftest.py` auto-fixtures:
  - `clean_global_caches()`: Clears module-level caches before/after tests
  - `test_env`: Mocks Qdrant to `:memory:`, clears API keys, mocks LLM functions
- Tests use `monkeypatch.setenv()` for isolation
- LLM mocks must be applied to BOTH source and consumer modules due to import-time binding

### Provider Fallback Chain
1. Tavily → DuckDuckGo → BrowserUseAdapter (scrape mode)
2. BrowserUse → Playwright → HTTP scraping

### Deep Research (`orchestration/deep_research/`)
- Multi-round search with query refinement
- Citation chaining for paper discovery
- Configured via `DeepResearchSettings`

### Code Execution Sandbox (`orchestration/code_sandbox/`)
- Extracts empirical claims from findings
- Verifies claims against code execution
- Configurable R/Julia support

### Multi-Modal Analysis (`multi_modal/`)
- Figure/table/equation extraction from PDFs
- Chart-to-text accessibility descriptions
- Pix2Text OCR for equation extraction

---

## Dependencies and Fallbacks

**Model fallback chain** (configured via `provider_priority`):
```
nvidia → ollama → openrouter → puter → vllm → openai → anthropic → gemini → groq
```

**NVIDIA integration**: `ENABLE_NVIDIA_MODEL=true` + `NVIDIA_API_KEY` enables hosted model in composer; falls back to deterministic local mode if unavailable.

---

## Artifact Output

Each completed run exports to `artifacts/<run_id>/`:
- `main.tex` - Main LaTeX document
- `references.bib` - Bibliography
- `compile_instructions.md` - Build instructions
- `summary.json` - Run metadata
