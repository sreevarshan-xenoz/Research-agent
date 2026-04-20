# Research Agent v2 - Technical Specification

## Overview
Research Agent v2 is a major upgrade introducing multi-provider LLM support, parallel subagent execution, 2-column IEEE format, and enhanced templating. This spec defines all new features, architecture changes, and migration paths from v1.

---

## 1. Document Format

### 1.1 Multi-Column Templates

#### 1.1.1 IEEE Two-Column Format
```latex
\documentclass[conference,twocolumn]{IEEEtran}
```

**Structure:**
- Title & Abstract: Full-width (one-column at top)
- Body: Two-column layout
- Figures/Tables: Full-width (`figure*`, `table*`) or single-column
- References: Two-column

**Implementation:**
- Update `src/research_agent/output/latex/templates/ieee/main.tex.j2`
- Add conditional `twocolumn` option based on template config
- Support mixed single/double column floats

#### 1.1.2 Template Selection API
```yaml
output:
  default_template: ieee          # ieee-1col, ieee-2col, acm, springer
  supported_templates:
    - ieee-1col
    - ieee-2col
    - acm
    - springer
  default_columns: 1                # 1 or 2
```

---

## 2. Multi-Provider LLM Architecture

### 2.1 Provider Tiers

| Role | Provider | Model | Use Case | Cost |
|------|---------|-------|----------|------|
| orchestrator | ollama (local) | qwen3:8b | Planning, routing, critic | Free |
| subagent | ollama (local) | deepseek-r1:8b | Section synthesis | Free |
| subagent | openrouter | qwen/qwen3-coder-32b-instruct:free | Heavy generation | Free tier |
| subagent | openrouter | google/gemma-3n-e4b-it:free | Fast inference | Free tier |
| subagent | puter (client-side) | ai21/jamba-large-1.7 | Fallback | Free |

### 2.2 Model Selection Strategy

#### 2.2.1 Priority-Based Selection
```
For each subagent task:
1. Check OLLAMA_AVAILABLE_MODELS → use local model if available
2. Fall back to OpenRouter free tier (20 req/min, 200/day)
3. Fall back to Puter.js client-side (no API key)
4. Return deterministic template if all fail
```

#### 2.2.2 Environment Variables
```bash
# Local Ollama
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_NUM_PARALLEL=4              # Concurrent requests per model
OLLAMA_MAX_LOADED_MODELS=2           # Max models in VRAM

# OpenRouter (free tier)
OPENROUTER_API_KEY=sk-or-...

# Provider priority order (comma-separated)
MODEL_PROVIDER_PRIORITY=ollama,openrouter,puter

# Per-role model overrides
ORCHESTRATOR_MODEL=ollama/qwen3:8b
SUBAGENT_MODEL=ollama/deepseek-r1:8b
FAST_SUBAGENT_MODEL=openrouter/google/gemma-3n-e4b-it:free
```

### 2.3 LiteLLM Integration

#### 2.3.1 Unified Client
```python
from litellm import completion

# Auto-failback across providers
response = completion(
    model="ollama/deepseek-r1:8b",  # Primary
    messages=[...],
    fallbacks=[
        {"model": "openrouter/qwen/qwen3-coder-32b-instruct:free"},
        {"model": "puter/ai21/jamba-large-1.7"}
    ]
)
```

#### 2.3.2 Router Configuration
```yaml
# litellm_config.yaml
model_list:
  - model_name: orchestrator
    litellm_params:
      model: ollama/qwen3:8b
      api_base: http://localhost:11434

  - model_name: subagent-local
    litellm_params:
      model: ollama/deepseek-r1:8b
      api_base: http://localhost:11434

  - model_name: subagent-cloud
    litellm_params:
      model: openrouter/qwen/qwen3-coder-32b-instruct:free
      api_key: os.environ/OPENROUTER_API_KEY
```

---

## 3. Parallel Subagent Execution

### 3.1 Architecture

```
                    ┌─────────────────┐
                    │  Planner Node   │
                    │  (qwen3:8b)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ Worker 1  │ │ Worker 2  │ │ Worker 3  │  ← Parallel
        │ (local)   │ │ (local)   │ │ (cloud)   │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
             │              │              │
             └──────────────┼──────────────┘
                            │
                    ┌──────▼──────┐
                    │ Combiner     │
                    └─────────────┘
```

### 3.2 Concurrency Configuration

| Hardware | `OLLAMA_NUM_PARALLEL` | `OLLAMA_MAX_LOADED_MODELS` | Max Concurrent |
|----------|------------------|----------------------|---------------|
| RTX 3090 (24GB) | 4 | 2 | 4 workers |
| RTX 4090 (24GB) | 4 | 2 | 4 workers |
| M2 Pro (16GB) | 2 | 1 | 2 workers |
| CPU only | 2 | 1 | 2 workers |

### 3.3 Worker Node Implementation

```python
# src/research_agent/orchestration/nodes/worker.py
class WorkerPool:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_parallel(self, tasks: list[Task]) -> list[Result]:
        async def run_task(task):
            async with self.semaphore:
                return await self.run_single(task)

        results = await asyncio.gather(*[
            run_task(t) for t in tasks
        ])
        return results
```

### 3.4 Task Distribution

```python
# Distribute tasks across providers based on complexity
def score_task_complexity(task: Task) -> int:
    """Complexity score 1-10"""
    if task.section_type == "related_work":
        return 8  # High - needs web search + synthesis
    if task.section_type == "background":
        return 6  # Medium
    if task.section_type == "methodology":
        return 7  # Medium-high
    return 5  # Default

def assign_provider(complexity: int) -> str:
    if complexity >= 7 and is_ollama_available():
        return "ollama/deepseek-r1:8b"  # Strong local
    elif is_openrouter_available():
        return "openrouter/qwen/qwen3-coder-32b-instruct:free"
    else:
        return "deterministic_fallback"
```

---

## 4. Paper Sources & Retrieval

### 4.1 Enhanced Provider List

| Provider | API | Free Tier | Rate Limit |
|----------|-----|-----------|------------|
| arxiv | ✅ | ✅ (official) | 3 req/sec |
| semantic_scholar | ✅ | ✅ (official) | 100/day |
| openalex | ✅ | ✅ (official) | 100k/year |
| google-scholar | ⚠️ | scrape | Limited |
| pubmed | ✅ | ✅ | 1 req/sec |

### 4.2 Retrieval Pipeline

```
Query → ArXiv Search → Fetch PDFs → Chunk → Embed → Qdrant
     → Semantic Scholar → Metadata → Cross-ref
     → OpenAlex → Author Network → Related
     → Web Search (fallback) → Scrape → Chunk
```

### 4.3 Configuration

```yaml
retrieval:
  web_provider: hybrid            # duckduckgo + browser_use
  web_search_depth: advanced     # fast, balanced, advanced
  paper_providers:
    - arxiv
    - semantic_scholar
    - openalex
  max_papers_per_section: 15
  chunk_size: 1024
  chunk_overlap: 128
  enable_fuzzy_dedup: true        # SHA1 fingerprint dedup
```

---

## 5. New Features

### 5.1 Real-Time Collaboration (Future)

- Session persistence in Redis
- WebSocket-based updates
- Multiple user presence

### 5.2 Citation Auto-Fix

```python
class CitationFixer:
    """Automatically fix broken Citations"""

    def __init__(self):
        self.semantic_scholar_api = SemanticScholarAPI()
        self.crossref_api = CrossRefAPI()

    async def fix_citation(self, citation: str) -> str:
        # Extract DOI or title
        doi = parse_doi(citation)
        if doi:
            return await self.lookup_doi(doi)

        # Try title search
        title = extract_title(citation)
        if title:
            return await self.lookup_title(title)

        return citation
```

### 5.3 Multi-Language Support

```yaml
# Templates per language
templates:
  ieee:
    languages:
      - en
      - zh
      - ja
  springer:
    languages:
      - en
      - de
      - fr
```

### 5.4 Figure Generation (Future)

- Mermaid diagram generation from descriptions
- PlantUML integration
- Matplotlib code generation

### 5.5 PDF Export

```python
# Direct PDF generation
def export_pdf(latex: str) -> bytes:
    """Use pdflatex or tectonic for PDF generation"""
    import tectonic

    result = tectonic(latex, ...)
    return result.pdf
```

---

## 6. Frontend Enhancements

### 6.1 Layout Changes

#### 6.1.1 Two-Column Workbench
```
┌─────────────────────────────────────────────────────────┐
│ Config (collapsible)  │  Workbench (main)   │ Chat    │
│                       │                     │         │
│ [Template ▼]          │ ┌─────┬─────┐       │         │
│ [Depth ▼]             │ │ Doc │ LaTeX│      │ Messages│
│ [Provider ▼]          │ └─────┴─────┘       │         │
│                       │                     │         │
│ [Overleaf] [Export]   │ [Evidence] [Stats]  │         │
└─────────────────────────────────────────────────────────┘
```

#### 6.1.2 Tab Changes
- **Doc Tab**: Quill editor with live preview
- **LaTeX Tab**: Raw LaTeX with syntax highlighting
- **Evidence Tab**: Section-by-section sources
- **Stats Tab**: Confidence scores, cost tracking

### 6.2 Provider Selector UI

```html
<select id="providerSelect">
  <option value="auto">Auto (best available)</option>
  <option value="ollama">Local Ollama</option>
  <option value="openrouter">OpenRouter Free</option>
  <option value="hybrid">Hybrid (parallel)</option>
</select>
```

### 6.3 Error Handling Improvements

```javascript
// Stream error display
function showStreamError(message) {
  const banner = document.createElement('div');
  banner.className = 'error-banner';
  banner.innerHTML = `
    <span class="error-icon">⚠</span>
    <span>${message}</span>
    <button onclick="this.parentElement.remove()">✕</button>
  `;
  document.body.appendChild(banner);
}

// Session expiry handling
async function checkSessionExpiry() {
  const response = await fetch('/api/session/ping');
  if (response.status === 410) {
    showStreamError('Session expired. Refreshing...');
    sessionId = null;
    await ensureSession();
  }
}
```

---

## 7. Performance Targets

| Metric | v1 | v2 Target | Improvement |
|--------|-----|-----------|-------------|
| Section generation time | ~45s | ~15s | 3x faster |
| Concurrent workers | 1 | 4 | 4x |
| Memory (Qdrant) | ~200MB | ~150MB | -25% |
| Free API calls | 0 | Unlimited | New |
| Template options | 2 | 5 | 2.5x |

---

## 8. Migration Path

### 8.1 Breaking Changes

| Change | Migration |
|--------|----------|
| Template v1 → v2 | Auto-detect based on `columns: 1|2` |
| `worker_model` env → `SUBAGENT_MODEL` | Deprecation warning added |
| Single model → multi-provider | Graceful fallback |

### 8.2 New Dependencies

```txt
# requirements.in
litellm>=1.50.0          # Unified LLM API
httpx[socks]>=0.28.0      # Async HTTP with proxy
tectonic>=0.21.0          # PDF generation
```

### 8.3 Backward Compatibility

```python
# Legacy env var support
if os.getenv("WORKER_MODEL"):
    warnings.warn("WORKER_MODEL is deprecated, use SUBAGENT_MODEL")
    os.environ.setdefault("SUBAGENT_MODEL", os.getenv("WORKER_MODEL"))
```

---

## 9. Configuration Schema (Updated)

```yaml
# configs/settings.v2.yaml
version: "2.0"

runtime:
  mode: api_only | parallel | async
  max_iterations: 4
  max_runtime_minutes: 25
  max_cost_usd: 5.0
  parallel_workers: 4           # NEW

models:
  orchestrator:
    provider: ollama
    model: qwen3:8b
  subagent:
    provider: auto               # NEW: auto-select
    local: deepseek-r1:8b
    cloud: openrouter/free

output:
  default_template: ieee-2col     # NEW
  supported_templates:
    - ieee-1col
    - ieee-2col
    - acm
    - springer
  default_columns: 2             # NEW

retrieval:
  web_provider: hybrid
  paper_providers:
    - arxiv
    - semantic_scholar
    - openalex

# NEW sections
features:
  cite_autofix: true
  parallel_subagents: true
  session_persistence: localStorage
```

---

## 10. Testing

### 10.1 Provider Fallback Tests

```python
@pytest.mark.asyncio
async def test_provider_fallback():
    # Test Ollama → OpenRouter → Puter → deterministic
    results = []

    # Try Ollama
    try:
        result = await generate("test", provider="ollama")
        results.append(result)
    except ProviderUnavailable:
        pass

    # Try OpenRouter
    try:
        result = await generate("test", provider="openrouter")
        results.append(result)
    except ProviderUnavailable:
        pass

    # Assert at least one succeeded
    assert len(results) >= 1
```

### 10.2 Parallel Execution Tests

```python
@pytest.mark.asyncio
async def test_parallel_workers():
    pool = WorkerPool(max_workers=4)
    tasks = [Task(section=f"section_{i}") for i in range(8)]

    results = await pool.execute_parallel(tasks)

    assert len(results) == 8
    # Verify they ran in parallel (check timestamps)
```

---

## 11. Roadmap

### Phase 1: Foundation (v2.0)
- [x] 2-column IEEE template
- [x] Multi-provider model selection
- [x] Parallel worker execution

### Phase 2: Reliability (v2.1)
- [ ] Citation autofix
- [ ] Session persistence
- [ ] Enhanced error handling

### Phase 3: Features (v2.2)
- [ ] PDF export
- [ ] Multi-language templates
- [ ] Real-time collaboration

### Phase 4: Scale (v2.3)
- [ ] Redis-backed state
- [ ] Multi-user support
- [ ] vLLM integration

---

## Appendix A: Free Model Reference

### Local (Ollama)
| Model | Size | VRAM | Best For |
|-------|------|------|---------|
| qwen3:8b | 4.7GB | 8GB | Orchestrator |
| deepseek-r1:8b | 4.7GB | 8GB | Reasoning |
| qwen2.5-coder:7b | 4.4GB | 7GB | Code generation |
| gemma3:4b | 2.5GB | 4GB | Fast inference |

### OpenRouter Free
| Model | Context | Best For |
|-------|---------|----------|
| qwen/qwen3-coder-32b-instruct | 32K | Code |
| google/gemma-3n-e4b-it | 8K | Fast |
| deepseek/deepseek-r1 | 64K | Reasoning |
| ai21/jamba-large-1.7 | 256K | Long context |

---

## Appendix B: Environment Variables Summary

```bash
# Required
OPENROUTER_API_KEY=sk-or-...          # For OpenRouter free tier

# Optional (Ollama defaults shown)
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=2

# v2 overrides
MODEL_PROVIDER_PRIORITY=ollama,openrouter,puter
ORCHESTRATOR_MODEL=ollama/qwen3:8b
SUBAGENT_MODEL=ollama/deepseek-r1:8b

# Feature flags
ENABLE_PARALLEL_SUBAGENTS=true
ENABLE_CITE_AUTOFIX=true
ENABLE_SESSION_PERSISTENCE=true
```

---

*Last Updated: April 2026*
*Version: 2.0-draft*