# Research Agent v2 — Strategic Roadmap

> **Last updated:** July 7, 2026
> **Status:** Active development — 45+ pipeline nodes, 8+ integrated providers, full research lifecycle automated
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
| **Verified Code Execution Sandbox** | ✅ | **P24** |
| **Security Hardening (RBAC, Audit, Rate Limit, SSO)** | ✅ | **P18** |
| **Automated Peer Review with Confidence Scoring** | ✅ | **P37** |
| **Multi-Model Ensemble Voting for Critical Tasks** | ✅ | **P31** |
| **Reproducibility Dashboard with Claim Filtering** | ✅ | **P29** |
| **Personal Research Library (Zotero/BibTeX/RIS/CSL JSON)** | ✅ | **P28** |
| **Paper-git Version Control with Diff/Branch/PR** | ✅ | **P36** |
| **Plugin System with Discovery and Lifecycle Hooks** | ✅ | **P19** |
| **PWA Mobile & Offline Support** | ✅ | **P20** |
| **Interactive Onboarding & Guided Tour** | ✅ | **P38** |

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

### ✅ P24 — Verified Code Execution Sandbox
**Completed July 2026.** Unique differentiator — isolated Docker sandbox with LLM-powered claim extraction, code generation, execution engine, and per-claim reproducibility reports.

**Key deliverables:**
- **New `code_sandbox/` module** (8 files): `DockerSandbox` with subprocess fallback, `ClaimExtractor`, `CodeGenerator`, `ExecutionEngine`, `ResultComparator`, `ReproducibilityReport`, graph node
- **Docker sandbox**: container warm pool, image management, Python/R/Julia support, memory limits
- **Claim extraction**: LLM identifies empirical claims with verification potential scoring from paper sections
- **Code generation**: LLM generates Python verification scripts per claim with dependency tracking
- **Execution engine**: runs code in Docker (fallback subprocess), captures stdout/stderr/timing
- **Result comparison**: numerical matching (5% tolerance) + LLM fallback for complex claims
- **Per-claim reproducibility report**: structured pass/fail/partial with evidence, exported to run artifacts
- **Config settings**: 10 config fields in `CodeSandboxSettings`
- **Graph integration**: wired between `exporter` and `code_execution` nodes

### ✅ P16 — Async Job Queue & Concurrency
**Completed July 2026.** Redis-backed async job queue with priority ordering, per-user concurrency limits, job lifecycle management, and REST API.

**Key deliverables:**
- **New `job_queue/` module** (4 files): `JobManager`, `Job` dataclass, `JobPriority`/`JobStatus`/`JobType` enums, standalone worker process
- **Redis priority queue**: uses Sorted Sets (zadd/zpopmin) with priority+FIFO scoring, per-user active job tracking
- **Job lifecycle**: enqueue → dequeue → running → complete/fail, with progress tracking, retries, and cancellation
- **5 REST API endpoints**: `GET /api/jobs/queue/health`, `POST /api/jobs` (enqueue), `GET /api/jobs` (list), `GET /api/jobs/{id}` (status), `POST /api/jobs/{id}/cancel`
- **Per-user concurrency limits**: configurable max concurrent runs per user (default 3)
- **Standalone worker**: `python -m research_agent.orchestration.job_queue.worker` with handlers for research_run, export, watchdog_check
- **Config settings**: 6 config fields in `JobQueueSettings`
- **Auth integration**: all endpoints protected with JWT auth + ownership checks

---

## Phase: Production Hardening

### ✅ P17 — Observability Stack
**Completed July 2026.** Full observability stack with Prometheus metrics, OpenTelemetry tracing, JSON structured logging, Sentry error tracking, and Grafana dashboards.

**Key deliverables:**
- **`observability/metrics.py`**: Prometheus counters/histograms/gauges for LLM requests, costs, latency, run duration
- **`observability/structured_log.py`**: JSON logging formatter with correlation IDs via contextvars
- **`observability/tracing.py`**: OpenTelemetry `init_tracing()` with OTLP HTTP exporter
- **`observability/error_tracking.py`**: Sentry integration with `init_sentry()` and `capture_message()` helper
- **Config**: `ObservabilitySettings` with Prometheus, OTel, Sentry fields + env var overrides
- **Grafana dashboard**: Pre-configured 10-panel dashboard (run stats, LLM latency, provider health)

**Estimated effort:** 2-3 sprints | **Deps:** P16

---

### ✅ P18 — Security Hardening
**Completed July 2026.** Full security stack with RBAC, SSO/OAuth, rate limiting, audit logging, and secrets encryption.

**Key deliverables:**
- **`security.py`**: RBAC role enums/viewer/editor/admin, `is_admin()`/`is_editor()` helpers, `require_role()` dependency factory, `set_user_role()` management, Fernet symmetric encryption (`encrypt_value`/`decrypt_value`) with deterministic SHA-256 key derivation
- **`audit.py`**: `AuditEntry` dataclass, `AuditStore` with JSONL daily-rotated files, `AuditMiddleware` for FastAPI with automatic action/resource classification, `GET /api/admin/audit` and `GET /api/admin/audit/stats` query endpoints
- **`rate_limit.py`**: `TokenBucket` implementation, `RateLimitStore` with auto-cleanup, `RateLimitMiddleware` with role-based tiers (60/300/1000 rpm for anonymous/auth/admin), per-endpoint overrides
- **`sso.py`**: OAuth provider definitions (Google, GitHub, ORCID), SSO router with provider listing, login URL generation, and callback scaffolding
- **`auth.py`**: Added `role: str = "viewer"` column to User model
- **`webapp.py`**: Auth context middleware (populates `request.state` from JWT), security middleware stack (rate limit → audit), SSO route integration, 7 admin API endpoints
- **Admin endpoints**: `GET /api/admin/audit`, `GET /api/admin/audit/stats`, `GET /api/admin/users`, `POST /api/admin/users/{id}/role`, `GET /api/admin/security/status`, `GET /api/admin/encrypt`, `GET /api/admin/decrypt`, `GET /api/admin/rate-limits`
- **Config schema**: `RBACSettings`, `RateLimitSettings`, `AuditSettings`, `SSOSettings`, `SecretsSettings` with env var overrides
- **Dependency**: Added `cryptography>=42.0.0` to pyproject.toml

**Estimated effort:** 3-4 sprints | **Deps:** Auth system

---

## Phase: Advanced RAG & Multi-Modal Intelligence

### ✅ P22 — Multi-Modal Paper Analysis
**Completed July 2026.** Full multi-modal extraction pipeline for figures, tables, equations, and charts.

**Key deliverables:**
- **Figure extraction & captioning** from PDFs (PyMuPDF + Vision LLM)
- **Table parsing & structured extraction** (pdfplumber)
- **Equation extraction & normalization** (Pix2Text / LaTeX-OCR)
- **Multi-modal Q&A**: "What does Figure 3 show?" with visual grounding
- **Chart-to-text generation** for accessibility

**Estimated effort:** 4-5 sprints | **Key differentiator**

---

### ✅ P23 — GraphRAG Knowledge Graph Retrieval
**Completed July 2026.** Persistent cross-run entity store with entity resolution/deduplication, multi-hop retrieval, interactive D3 force-directed graph explorer, time-based landscape evolution, and semantic search.

**Key deliverables:**
- **Persistent `KnowledgeGraphStore`** (NetworkX-based): entity resolution, deduplication, multi-hop retrieval (`get_multi_hop_retrieval()`), landscape evolution (`get_landscape_evolution()`), explorer export (`export_for_explorer()`)
- **Interactive graph explorer** (`kg_explorer.html`): D3 force-directed layout with zoom/pan, drag, link arrowheads, color-coded node types (Paper/Author/Method/Dataset/Task), tooltip on click with connected node highlighting, legend, reset/toggle/export controls
- **Wired into graph pipeline**: `knowledge_graph_node` now instantiates `KnowledgeGraphStore` and persists entities/relations after each run's combiner phase
- **3 API endpoints**: `GET /api/knowledge-graph/data` (node-link JSON), `GET /api/knowledge-graph/explorer` (HTML page), `GET /api/knowledge-graph/landscape` (time-based evolution), `GET /api/knowledge-graph/search` (semantic query)
- **Web UI integration**: KG tab button in workbench, iframe-based explorer panel, wired into `app.js` with `loadKgExplorer()` function

**Estimated effort:** 4-5 sprints | **Key differentiator** ✅ *P14 subsumed into P23*

---

## Phase: Human-Centric Collaboration & UX

### ✅ P25 — Collaborative Real-Time Co-Editing
**Completed July 2026.** Full CRDT-based real-time co-editing using Yjs with y-py Python backend, section locking, comment threads, cursor presence, and version history with snapshots.

**Key deliverables:**
- **Yjs WebSocket server** (`yjs_server.py`): Python-based Yjs sync protocol handler using `y-py` bindings. Manages per-document rooms, sync step1/step2 handshake, update broadcasting, awareness relay, and file-system persistence for document recovery
- **Section locking API** (`collab_routes.py`): REST endpoints for acquiring/releasing per-section locks with 5-minute TTL, conflict detection, and multi-user exclusion
- **Comment threads API**: Add, list, resolve, and delete comments per section with reply support and persistence
- **Version history API**: Create named snapshots, list history, view snapshot content, rollback to any snapshot, and line-based diff viewer
- **Frontend collaborative editor** (`collaborative-editor.js`): IIFE module integrating Yjs with Quill.js via y-quill binding, lazy-loads Yjs/y-websocket/y-quill/QuillCursors from CDN, provides cursor presence awareness, section lock UI controls, comment input panel, and snapshot/rollback controls
- **Web UI integration**: Collab status bar in Document Editor with live user counter, section dropdown + lock button, comments panel, version history panel, and snapshot creation button
- **CSS polish**: Status indicators (connected/connecting/locked/error), comment cards with resolve actions, version history cards with rollback buttons
- **Dependency**: Added `y-py>=0.6.0` to pyproject.toml

**Estimated effort:** 5-6 sprints | **Deps:** WebSocket infra exists

---

### ✅ P27 — Multi-Format Submission Pipeline
**Completed July 2026.** Full submission pipeline with format conversion, style compliance checking, content adaptation, and one-click export.

**Key deliverables:**
- **Format converter** (`format_converter.py`): IEEE ↔ ACM ↔ Springer ↔ Elsevier LaTeX format conversion using LLM with template-specific rules
- **Style compliance checker** (`style_checker.py`): 10-point validation including required sections, page limits, reference counts, figure/table limits, forbidden packages, abstract word count, title length, format-specific checks (CCS concepts for ACM, pubid for IEEE), and common LaTeX errors (unmatched braces, unclosed environments, non-ASCII characters)
- **Content adapter** (`content_adapter.py`): Auto-wrap content to match template constraints (section reorganization, bibliography format, figure wrapping, abstract shortening)
- **Submission pipeline** (`submission_pipeline.py`): Full-stack orchestration — format conversion → style check → content adaptation → ZIP export, with per-run artifact handling
- **API endpoints** (`submission_routes.py`): `POST /api/submission/style-check`, `POST /api/submission/convert`, `POST /api/submission/adapt`, `POST /api/submission/pipeline`, `GET /api/submission/export-zip/{run_id}`, `GET /api/submission/formats`
- **Frontend UI**: Submission tab in workbench with format selector, style check results (score, errors, warnings, info), issue cards with severity colors, download .tex / download ZIP export buttons
- **Web UI**: Full submission panel in index.html, wired into app.js with `loadSubmissionPipeline()` function, CSS styling in styles_premium.css

**Estimated effort:** 3-4 sprints

---

### ✅ P28 — Personal Research Library
**Completed July 2026.** Full personal library with Zotero/BibTeX import, LLM auto-tagging, smart collections, PDF annotations, reading list, multi-format export, and multi-select.

**Key deliverables:**
- **Zotero import** via API key + CSL JSON/BibTeX/RIS file upload
- **LLM auto-tagging** with topic classification and suggested tags
- **Smart collections** with rule builder (field/operator/value, AND logic)
- **PDF annotation viewer** with highlights, notes, comments, color coding
- **Reading list management** (to-read, reading, completed, skipped) with priority and progress tracking
- **Multi-format export**: BibTeX (.bib), RIS (.ris), CSL JSON (.json) with format selector dropdown
- **Multi-select checkboxes**: batch select with Select All/Clear, export checked items
- **Copy as BibTeX**: one-click clipboard copy in item detail view

---

### ✅ P29 — Reproducibility Dashboard
**Completed July 2026.** Full reproducibility dashboard with score cards, per-claim results, claim filtering by status, text search, sort controls, Markdown + JSON export, and run history comparison.

**Key deliverables:**
- **Claim filtering by status**: interactive chips for All/Passed/Failed/Partial/Unverifiable with real-time re-rendering
- **Claim text search**: real-time search across claim text, claimed values, and actual values
- **Sort controls**: sort by confidence (asc/desc), runtime (asc/desc), or alphabetically
- **Download/export**: Download Report (Markdown) + JSON Export buttons with Blob downloads
- **Run history comparison**: loads reproducibility scores from past sessions with clickable history items to load a different run
- **Score cards**: 5 metric cards (overall score, passed, failed, partial, unverifiable)
- **Per-claim cards**: status emoji, claim text, claimed/actual values, confidence %, runtime
- **Verdict banner**: color-coded strong/partial/poor reproducibility verdict
- **CSS polish**: hover micro-interactions, filter chip active states, slide-in animations

**Estimated effort:** 2-3 sprints | **Leverages:** existing P24 Code Sandbox artifact structure and 4 API endpoints

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

### ✅ P36 — Paper-git: Version Control for Research
**Completed July 2026.** Full version control system with snapshot timeline, branch management, PR review workflow, and diff viewer.

**Key deliverables:**
- **Git-like diff** for LaTeX documents with colored hunks (additions/deletions/modifications)
- **Branch/merge** for research experiments with snapshot selection
- **Checkpoint restore** per run/section with timeline grouped by branch
- **Collaborative review workflow** (PR-style): approve, request changes, merge, close, threaded comments
- **Diff viewer**: two-snapshot selector with Compare button, file-level diff rendering
- **Full frontend UI**: 4 sub-tabs (Timeline, Branches, Pull Requests, Diff Viewer) with inline rendering

---

### ✅ P17 — Observability Stack
**Completed July 2026.** Full observability stack with Prometheus metrics, OpenTelemetry tracing, JSON structured logging, Sentry error tracking, and Grafana dashboards.

**Key deliverables:**
- **`observability/metrics.py`**: Prometheus counters/histograms/gauges for LLM requests, costs, latency, run duration
- **`observability/structured_log.py`**: JSON logging formatter with correlation IDs via contextvars
- **`observability/tracing.py`**: OpenTelemetry `init_tracing()` with OTLP HTTP exporter
- **`observability/error_tracking.py`**: Sentry integration with `init_sentry()` and `capture_message()` helper
- **Grafana dashboard**: 10-panel dashboard (run stats, LLM latency, provider health)
- **Config schema**: `ObservabilitySettings` with Prometheus, OTel, Sentry fields
- **Wired into**: `webapp.py` (lifespan init, /metrics endpoint), `llm_client.py` (per-call metrics), `graph.py` (run duration histogram)

### ✅ P37 — Automated Peer Review with Confidence Scoring
**Completed July 2026.** Multi-persona peer review with structured templates, per-section heuristic confidence scoring, meta-review aggregation, and 3 simulated reviewer personas.

### ✅ P31 — Multi-Model Ensemble Voting for Critical Tasks
**Completed July 2026.** Runs N models from different providers in parallel on the same prompt and aggregates responses using configurable voting strategies. Wired into 5 critical graph nodes.

**Key deliverables:**
- **`models/ensemble.py`**: Core ensemble voter with 3 voting strategies (Majority, Weighted, Consensus), parallel async model calls with provider diversity, rate limiter integration for 5 cloud providers, and robust single-model fallback
- **Config schema**: `EnsembleSettings` with 4 config fields and per-task overrides for critic, planner, composer, bias_detection, hallucination_guard
- **Ensemble config env vars**: `ENSEMBLE_ENABLED`, `ENSEMBLE_NUM_MODELS`, `ENSEMBLE_TIMEOUT`, `ENSEMBLE_MIN_SUCCESS_RATIO`
- **5 wired graph nodes**: critic (weighted, 3 models), planner (majority, 2 models), composer (consensus, 3 models), bias_detector (majority, 3 models), hallucination_guard (weighted, 3 models)
- **Admin API endpoints**: `GET /api/admin/ensemble/status` (config + model health), `POST /api/admin/ensemble/test` (test round with per-vote detail)

**Key deliverables:**
- **`peer_review/models.py`**: Dataclasses for `ReviewCriterion`, `ReviewSection`, `PersonaReview`, `MetaReview` with JSON serialization
- **`peer_review/personas.py`**: 3 reviewer personas (Theoretical, Applied, Experimental) with unique rubrics, focus areas, and emphasis weights
- **`peer_review/scorer.py`**: Heuristic per-section confidence scoring (length, citations, coherence, academic language) with section-type weighted rubrics
- **`peer_review/aggregator.py`**: Meta-review aggregation with variance computation, weighted consensus scoring, deduplicated strength/weakness aggregation, and disagreement detection
- **`peer_reviewer.py`**: Rewritten graph node that runs 3 persona reviews via LLM, parses structured JSON responses, scores sections, and aggregates into a combined report
- **State fields**: `peer_reviews` (list of individual reviews), `peer_review_meta` (aggregated meta-review), `peer_review_personas` (personas used)
- **Exporter**: Writes `peer_reviews.json` and `peer_review_meta.json` alongside existing `peer_review.md`

**Estimated effort:** 2-3 sprints

---

### ✅ P38 — Interactive Tutorial & Onboarding
**Completed July 2026.** Frontend-only onboarding system with guided tour, contextual tooltips, sample topics panel, and welcome overlay for first-time users.

**Key deliverables:**
- **`onboarding_guide.js`**: IIFE-wrapped self-contained module with guided tour (11 steps), contextual tooltips (22 elements), sample topics panel (6 pre-defined research topics with one-click pre-fill), and welcome overlay for first-time users
- **Guided tour**: Step-by-step walkthrough of sidebar, pipeline tracker, workbench tabs, document editor, LaTeX source, PDF preview, research chat, modes, config panel, kanban board, and session controls
- **Contextual tooltips**: 22 hover/focus tooltip definitions for all key UI elements
- **Sample topics**: 6 one-click research topics with auto-fill
- **Welcome overlay**: Full-screen backdrop with feature grid, 3 action buttons, "Don't show again" checkbox

---

## New: Plugin System & Extensibility

### ✅ P19 — Plugin System
**Completed July 2026.** Full plugin system with entry-point discovery, lifecycle hooks, marketplace UI, sandboxed execution, and community registry.

**Key deliverables:**
- **Entry-point based plugin discovery** (Python namespace packages via `research_agent.plugins` entry point)
- **Plugin lifecycle hooks**: `on_run_start`, `on_section_generated`, `on_run_complete`, `on_tool_call`
- **Plugin marketplace** UI for browsing/installing with enabled/disabled toggle
- **Sandboxed plugin execution** with isolated subprocess
- **Community plugin registry** with versioning and dependency resolution
- **Web UI**: Full plugin manager panel with list, detail view, settings form, hook listing, enable/disable toggle

---

### ✅ P20 — Mobile & Offline Support (PWA)
**Completed July 2026.** Full PWA with manifest, service worker, offline fallback, background sync, and mobile-responsive UI.

**Key deliverables:**
- **PWA manifest** (`manifest.json`): app name, SVG icons (192/512), theme color, shortcuts, display modes
- **Service worker** (`service-worker.js`): cache-first for static/CDN, network-first for API, offline navigation fallback, background sync for library data
- **Offline fallback page** (`offline.html`): styled dark theme with animated status dot, retry button
- **Service worker registration**: update prompt toast with controller change auto-reload
- **API data pre-caching**: pre-fetches library/reading list data after auth for offline use
- **Mobile-responsive UI**: viewport meta tags, apple-mobile-web-app support
- **Backend routes**: `/manifest.json`, `/service-worker.js`, `/offline.html` at root scope with proper headers

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
Sprint 3-4:              P22 Multi-Modal Analysis → P17 Observability (Complete)
Sprint 5-6:              P23 GraphRAG → P28 Personal Library (Complete)
Sprint 7-8:              P25 Co-Editing → P27 Submission Pipeline → P18 Security (Complete)
Sprint 9-10:             P19 Plugin System → P20 PWA → P36 Paper-git (Complete)
Sprint 11+:              P26 Advanced Agentic → P34 Swarm → P35 Cross-Lingual
```

### First-Mover Advantage Features

| Rank | Feature | Differentiation | Effort |
|------|---------|----------------|--------|
| ⭐ | **P24 Verified Code Sandbox** | ✅ Completed — Claim verification via code execution | 3-4 sprints |
| 🥇 | **P22 Multi-Modal RAG** | ✅ Completed — Figure/table/equation understanding | 4-5 sprints |
| ✅ | **P21 Deep Research Engine** | ✅ Completed — Iterative query refinement + citation chaining | 3-4 sprints |
| 🥉 | **P23 GraphRAG** | ✅ Completed — Cross-run knowledge graphs | 4-5 sprints |
| 💡 | **P36 Paper-git** | ✅ Completed — Research artifact versioning | 3-4 sprints |
| 🔌 | **P19 Plugin System** | ✅ Completed — Community plugin marketplace | 3 sprints |

### Quick Wins (1-2 sprints each)

| Feature | Effort | Why Quick |
|---------|--------|-----------|
| **P29 Reproducibility Dashboard** | ✅ Completed | 2-3 sprints |
| **P37 Peer Review with Confidence** | ✅ Completed | 2-3 sprints |
| **P38 Onboarding System** | ✅ Completed | 2-3 sprints |
| **P28 Personal Library** | ✅ Completed | 4-5 sprints |
| **P20 Mobile & Offline (PWA)** | ✅ Completed | 3-4 sprints |
| **P39 Research Templates** | 2-3 sprints | Template-based, no new infra |
| **P40 Research Team Management** | 3-4 sprints | Multi-user workspaces
