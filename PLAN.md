# Research Agent v2 — Strategic Roadmap

> **Last updated:** July 4, 2026
> **Status:** Active development — 30+ pipeline nodes, 8+ integrated providers, full research lifecycle automated
> **Research sources:** STORM, GPT-Researcher, Agent Laboratory, AI-Researcher, Elicit, Scite, Consensus, NotebookLM, GraphRAG, MG²-RAG, MiA-RAG

---

## Current Capabilities

The project delivers a complete research lifecycle pipeline with all features live:

| Capability | Status | Phase |
|-----------|--------|-------|
| Topic intake & clarification | ✅ | P0 |
| Planner + parallel workers | ✅ | P0 |
| Deep RAG (Qdrant) indexing | ✅ | P0 |
| Critic + iterative replanning | ✅ | P0 |
| Section synthesis & combination | ✅ | P0 |
| LaTeX composition (IEEE/ACM/Beamer/Poster) | ✅ | P0 |
| Citation verification & auto-fix | ✅ | P0 |
| Formula normalization & verification | ✅ | P0 |
| Hallucination guard | ✅ | P0 |
| Peer review automation | ✅ | P0 |
| Bias detection | ✅ | P0 |
| Knowledge graph construction | ✅ | P0 |
| Future work extrapolation | ✅ | P0 |
| Comparison table generation | ✅ | P0 |
| Figure generation (Mermaid/TikZ) | ✅ | P0 |
| Paper-to-Blog/Newsletter/Twitter export | ✅ | P0 |
| Interactive LaTeX preview | ✅ | P0 |
| Multi-paper survey generation | ✅ | P0 |
| Research Q&A chatbot (PDF library) | ✅ | P0 |
| Code execution & reproducibility | ✅ | P0 |
| Citation network visualization | ✅ | P0 |
| Dataset discovery (HF/Kaggle) | ✅ | P0 |
| Grant proposal generator | ✅ | P0 |
| Research trends dashboard | ✅ | P0 |
| Overleaf push/pull | ✅ | P0 |
| Plagiarism checker | ✅ | P0 |
| Voice intake | ✅ | P0 |
| Auth + session persistence | ✅ | P0 |
| WebSocket real-time streaming | ✅ | P0 |
| Watchdog literature monitoring | ✅ | P0 |
| **Agentic Chat with Tool-Calling Loop** | ✅ | **P15** |
| **AI Model Router with Multi-Provider Fallback** | ✅ | **P12** |
| **Automated Literature Monitoring & Alerting** | ✅ | **P13** |
| **Agentic Deep Research Engine** | ✅ | **P21** |

---

## Current Codebase Health

| Metric | Status | Details |
|--------|--------|---------|
| **Ruff lint** | ✅ PASS | 0 errors across all source files |
| **Mypy typecheck** | ✅ PASS | 0 errors across all source files |
| **Tests (unit)** | ✅ PASS | All unit tests passing |
| **Tests (integration)** | 🟡 Needs work | Existing smoke test times out (hangs on tool call), more coverage needed |
| **Coverage** | 🟡 Partial | No integration tests with real graph execution through tools |
| **Docs** | 🟡 Needs work | Inline docstrings good, but no user-facing documentation website |

---

## Recently Completed

### ✅ P15 — Intelligent Research Assistant (Agentic Chat)
**Completed July 2026.** Full agentic chat with tool-calling, cross-session memory, proactive suggestions, streaming, research planning mode, and feedback buttons.

**Key deliverables:**
- Tool-calling agent loop (`chat/agent.py`) with multi-tool orchestration
- Cross-session memory (`chat/memory.py`) with Redis fallback
- Research planning mode (`/api/chat/plan`) with plan panel in composer
- Streaming agentic chat (`/api/chat/agent/stream`) with NDJSON events
- User feedback buttons (`/api/chat/feedback`) + thumbs up/down UI

### ✅ P12 — AI Model Router & Multi-Provider Support
**Completed July 2026.** Smart model router with 6+ provider adapters, cost tracking, latency-aware routing, embedding fallback chain, and Settings UI.

**Key deliverables:**
- **Provider adapters**: Ollama, OpenRouter, NVIDIA, vLLM, OpenAI, Anthropic, Google Gemini, Groq
- **Model router YAML config** (`ModelRouterSettings`): map task types (`plan`, `write`, `critique`, `code`, `embed`) to specific models
- **Cost tracking module** (`models/cost_tracker.py`): per-run budget enforcement, pricing tables for 15+ models
- **Latency-aware routing** (`models/latency_tracker.py`): sliding-window response time tracking, auto-selects fastest provider
- **Settings UI**: collapsible model preferences panel, per-provider API keys, health check button
- **Embedding fallback chain**: sentence-transformers → OpenAI → NVIDIA → deterministic mock
- **Live `/api/health/models` endpoint**: tests all configured providers, returns status + latency + cost metrics

### ✅ P13 — Automated Literature Monitoring & Alerting
**Completed July 2026.** Background scheduler with true diff detection, relevance scoring, email digests, and dashboard widget.

**Key deliverables:**
- **Background scheduler** (APScheduler integration): polls ArXiv + Semantic Scholar on configurable interval
- **True fingerprint-based diff detection**: `_compute_fingerprint()` avoids re-reporting seen papers
- **Relevance scoring**: `_compute_relevance_score()` — weighted multi-factor (topic/keyword/author/venue/recency)
- **Email digest generator** (`digest_email.py`): rich HTML emails with dark theme, relevance badges, paper count
- **SMTP configuration** via `WatchdogEmailSettings` + env var overrides
- **Dashboard widget**: "Latest Papers" panel in sidebar with digest cards, refresh/check buttons
- **New API endpoints**: `GET /api/watchdog/dashboard`, `GET/POST /api/watchdog/notifications/{id}`, `POST /api/watchdog/deep-dive`, `POST /api/watchdog/email/test`
- **Per-profile notification preferences** (frequency, email, min relevance threshold)
- **One-click deep dive**: launch full `run_graph` from a discovered paper

### ✅ P21 — Agentic Deep Research Engine
**Completed July 2026.** Self-correcting search loop with iterative query refinement, citation chaining, and multi-factor evidence scoring integrated into the core orchestration graph.

**Key deliverables:**
- **New `deep_research/` module** (`query_refiner.py`, `citation_chainer.py`, `evidence_scorer.py`, `termination.py`)
- **Iterative query refinement**: LLM analyzes gaps after each search pass, generates 1–2 follow-up queries per task
- **Citation chaining**: BFS recursive fetch of citing + cited papers (via Semantic Scholar API), up to configurable depth
- **Multi-factor evidence scoring**: coverage (35%), source authority (25%), recency (15%), citation impact (15%), provider diversity (10%), with contradiction penalty
- **Search termination heuristics**: novelty decay curve + score plateau detection + min coverage safety net
- **Deep Research Settings** (`config/schema.py`): 9 config fields (rounds, chain depth, scoring thresholds, etc.)
- **Worker integration**: `_run_deep_research_task()` replaces single-pass search with multi-round refinement loop
- **Critic upgrade**: from simple `item_count / 8.0` to 5-factor weighted scoring
- **State fields**: `search_rounds`, `termination_signals`, `chained_papers`, `chained_paper_ids`

---

## Next Up: Core Infrastructure & Agentic Features

### P24 — Verified Code Execution Sandbox
**Why:** ⭐ Unique differentiator — no other research tool verifies paper claims by executing code.

**What to build:**
- [ ] **Docker sandbox** for safe code execution (Python, R, Julia)
- [ ] **Claim extraction from paper**: identify empirical claims with code verification potential
- [ ] **Code generation from claim descriptions**: LLM generates verification scripts
- [ ] **Execution engine**: run code in isolated container, capture stdout/stderr/timings
- [ ] **Result comparison**: compare empirical results against paper claims
- [ ] **Reproducibility report**: per-claim pass/fail/partial with evidence
- [ ] **Integration with graph**: auto-trigger for sections with high empirical content

**Estimated effort:** 3-4 sprints
**Why now:** First-mover advantage. Builds on existing code execution node.

---

## Phase: Production Hardening

### P16 — Async Job Queue & Concurrency
- [ ] **Celery/RQ job queue** for background research runs
- [ ] **Job priority**: interactive chat high priority, deep research low priority
- [ ] **Concurrent run limits** per user with fair scheduling
- [ ] **Run cancellation** via API
- [ ] **Kubernetes HPA integration** for elastic scaling

**Estimated effort:** 2-3 sprints | **Deps:** Redis

---

### P17 — Observability Stack
- [ ] **OpenTelemetry instrumentation** across all nodes
- [ ] **Prometheus metrics** (run duration, LLM latency, error rates, cost per run)
- [ ] **Grafana dashboards** (research pipeline overview, cost breakdown, provider health)
- [ ] **Structured logging** (JSON logs with correlation IDs)
- [ ] **Sentry/error tracking** integration

**Estimated effort:** 2-3 sprints | **Deps:** P16

---

### P18 — Security Hardening
- [ ] **RBAC** (viewer/editor/admin roles)
- [ ] **SSO/OAuth** (Google, GitHub, ORCID)
- [ ] **API rate limiting** per user/endpoint
- [ ] **Audit logging** for all research actions
- [ ] **Secrets management** (encrypted API key storage)

**Estimated effort:** 3-4 sprints | **Deps:** Auth system

---

## Phase: Advanced RAG & Multi-Modal Intelligence

### P22 — Multi-Modal Paper Analysis
- [ ] **Figure extraction & captioning** from PDFs
- [ ] **Table parsing & structured extraction** (camelot/tabula)
- [ ] **Equation extraction & normalization** (LaTeX-OCR)
- [ ] **Multi-modal Q&A**: "What does Figure 3 show?" with visual grounding
- [ ] **Chart-to-text generation** for accessibility

**Estimated effort:** 4-5 sprints | **Key differentiator**

---

### P23 — GraphRAG Knowledge Graph Retrieval
- [ ] **Persistent entity store** across runs (Neo4j or NetworkX serialized)
- [ ] **Entity resolution/deduplication** across papers
- [ ] **Multi-hop retrieval**: "What papers cite the method used in Paper X?"
- [ ] **Interactive graph explorer** (three.js or Sigma.js)
- [ ] **Time-based landscape evolution**: animate research trends over years

**Estimated effort:** 4-5 sprints | **Key differentiator**

---

### P14 — Research Knowledge Graph Explorer
- [ ] **Persistent graph store** (Neo4j/NetworkX)
- [ ] **Entity deduplication** across runs
- [ ] **Interactive graph explorer** (three.js or Sigma.js)
- [ ] **Semantic search** over the KG
- [ ] **Time-based animation** of research landscape evolution

**Estimated effort:** 4-5 sprints | **Note:** P23 subsumes this — prioritize P23 instead

---

## Phase: Human-Centric Collaboration & UX

### P25 — Collaborative Real-Time Co-Editing
- [ ] **CRDT-based co-editing** via WebSocket (Yjs)
- [ ] **Per-section locking** and conflict resolution
- [ ] **Comment threads** on paper sections
- [ ] **Cursor presence**: see who's editing what in real-time
- [ ] **Version history** with diff viewer and rollback

**Estimated effort:** 5-6 sprints | **Deps:** WebSocket infra exists

---

### P27 — Multi-Format Submission Pipeline
- [ ] **Format converters**: IEEE ↔ ACM ↔ Springer ↔ Elsevier
- [ ] **Style compliance checker**: validate against conference guidelines
- [ ] **Auto-wrap content** to match template constraints
- [ ] **One-click export** for Overleaf, arXiv, conference submission

**Estimated effort:** 3-4 sprints

---

### P28 — Personal Research Library
- [ ] **Zotero import** via CSL/BibTeX
- [ ] **Auto-tagging** with LLM-based topic classification
- [ ] **Smart collections** based on research themes
- [ ] **PDF annotation viewer** with highlights and notes
- [ ] **Reading list management** (to-read, reading, completed)

**Estimated effort:** 4-5 sprints

---

### P29 — Reproducibility Dashboard
- [ ] **Experiment tracking** across runs
- [ ] **Result comparison** side-by-side
- [ ] **Run artifact explorer** (browse all generated files per run)
- [ ] **Research timeline view** (when/what was researched)

**Estimated effort:** 2-3 sprints

---

### P26 — Advanced AI Research Assistant
- [ ] **Autonomous mode**: agent proposes research agenda without user prompting
- [ ] **Hypothesis generation**: LLM synthesizes novel research hypotheses from gaps
- [ ] **Research strategy recommendation**: suggest methodology, datasets, baselines
- [ ] **Proactive gap filling**: when literature is thin, suggest pilot experiments

**Estimated effort:** 5-6 sprints

---

## Phase: Cutting-Edge Research Features

### P34 — Multi-Agent Research Swarm
- [ ] **Role-specialized agents**: Theorist, Experimentalist, Critic, Editor
- [ ] **Debate protocol**: agents discuss and refine hypotheses
- [ ] **Consensus mechanisms**: voting/weighting agent outputs
- [ ] **Swarm coordination**: dynamic task allocation across agents
- [ ] **Self-improvement**: agents learn from past run outcomes

**Estimated effort:** 5-6 sprints

---

### P35 — Cross-Lingual Research & Translation
- [ ] **Multilingual embeddings** for non-English paper discovery
- [ ] **Translation pipeline**: paper abstracts/sections → target language
- [ ] **Cross-lingual Q&A**: ask in English, answer from Chinese/Japanese/German papers
- [ ] **Bilingual paper generation**: LaTeX with parallel text columns

**Estimated effort:** 4-5 sprints

---

### P36 — Paper-git: Version Control for Research
- [ ] **Git-like diff** for LaTeX documents
- [ ] **Branch/merge** for research experiments
- [ ] **Checkpoint restore** per run/section
- [ ] **Collaborative review workflow** (PR-style)
- [ ] **Conflict resolution UI** for parallel edits

**Estimated effort:** 3-4 sprints

---

### P37 — Automated Peer Review with Confidence Scoring
- [ ] **Structured review template** (strengths, weaknesses, questions)
- [ ] **Per-section confidence scoring** (0.0-1.0)
- [ ] **Review aggregation**: multiple reviews into meta-review
- [ ] **Reviewer persona simulation**: theoretical vs. applied vs. experimental reviewer

**Estimated effort:** 2-3 sprints

---

### P38 — Interactive Tutorial & Onboarding
- [ ] **Guided tour** of research pipeline
- [ ] **Sample topics** with pre-loaded results
- [ ] **Command palette** for power users
- [ ] **Tooltips and contextual help** throughout UI
- [ ] **Quick-start templates**: "Research a paper topic", "Compare methods", "Find datasets"

**Estimated effort:** 2-3 sprints

---

## New: Plugin System & Extensibility

### P19 — Plugin System
- [ ] **Entry-point based plugin discovery** (Python namespace packages)
- [ ] **Plugin lifecycle hooks**: `on_run_start`, `on_section_generated`, `on_run_complete`
- [ ] **Plugin marketplace** UI for browsing/installing
- [ ] **Sandboxed plugin execution** for safety
- [ ] **Community plugin registry** with versioning

**Estimated effort:** 3 sprints

---

### P20 — Mobile & Offline Support
- [ ] **PWA manifest** for installable web app
- [ ] **Service worker** for offline caching
- [ ] **Local-first architecture** (IndexedDB for offline state)
- [ ] **Background sync** when connectivity restored
- [ ] **Mobile-responsive UI** for phone/tablet

**Estimated effort:** 3-4 sprints

---

### P39 — Research Templates & Presets
- [ ] **Research template library**: Literature Survey, Meta-Analysis, Systematic Review, Case Study
- [ ] **Conference preset packs**: CVPR, NeurIPS, ICML, ACL formatting presets
- [ ] **Custom template builder**: drag-and-drop research pipeline designer
- [ ] **Template marketplace**: share and discover community templates

**Estimated effort:** 2-3 sprints

---

### P40 — Research Team Management
- [ ] **Team workspaces**: shared research projects
- [ ] **Task assignment**: assign sections/tasks to team members
- [ ] **Activity feed**: what everyone is working on
- [ ] **Shared resource pool**: common paper library, datasets, API keys

**Estimated effort:** 3-4 sprints

---

## Strategic Sequencing

```
Sprint NOW (Complete):   P12 Model Router → P15 Agentic Chat → P13 Literature Mon.
                         ╔═══════════════════════════════════════════════╗
                         ║  ↓ These features are scoped for implementation  ║
                         ╚═══════════════════════════════════════════════╝
Sprint NOW (Complete):   P21 Deep Research Engine (iterative search + citation chaining)
Sprint 1-2:              P24 Code Sandbox (unique differentiator)
                           → P16 Job Queue (infrastructure)
Sprint 3-4:              P22 Multi-Modal Analysis → P17 Observability
Sprint 5-6:              P23 GraphRAG → P28 Personal Library
Sprint 7-8:              P25 Co-Editing → P27 Submission Pipeline → P18 Security
Sprint 9+:               P26 Advanced Agentic → P34 Swarm → P19 Plugins
```

### First-Mover Advantage Features

| Rank | Feature | Differentiation | Effort |
|------|---------|----------------|--------|
| ⭐ | **P24 Verified Code Sandbox** | No other tool verifies paper claims by executing code | 3-4 sprints |
| 🥇 | **P22 Multi-Modal RAG** | Figure/table/equation understanding is the next frontier | 4-5 sprints |
| ✅ | **P21 Deep Research Engine** | ✅ Completed July 2026 — iterative query refinement + citation chaining | 3-4 sprints |
| 🥉 | **P23 GraphRAG** | Cross-run knowledge graphs for multi-hop reasoning | 4-5 sprints |
| 💡 | **P36 Paper-git** | Research artifact versioning is an unmet need | 3-4 sprints |
| 🔌 | **P19 Plugin System** | Enables community contributions and marketplace | 3 sprints |

### Quick Wins (1-2 sprints each)

| Feature | Effort | Why Quick |
|---------|--------|-----------|
| **P29 Reproducibility Dashboard** | 2-3 sprints | Leverages existing artifact structure |
| **P37 Peer Review with Confidence** | 2-3 sprints | Builds on existing peer review node |
| **P38 Onboarding System** | 2-3 sprints | Frontend-only, no backend changes |
| **P39 Research Templates** | 2-3 sprints | Template-based, no new infra
