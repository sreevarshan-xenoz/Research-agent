# Research Agent v2 — Strategic Roadmap

> **Last updated:** June 27, 2026
> **Status:** Active development — 20+ pipeline nodes, 8 integrated services, full research lifecycle automated
> **Research sources:** STORM, GPT-Researcher, Agent Laboratory, AI-Researcher, Elicit, Scite, Consensus, NotebookLM, GraphRAG, MG²-RAG, MiA-RAG

---

## Current Capabilities

The project already delivers a complete research lifecycle pipeline:

| Capability | Status |
|-----------|--------|
| Topic intake & clarification | ✅ Live |
| Planner + parallel workers | ✅ Live |
| Deep RAG (Qdrant) indexing | ✅ Live |
| Critic + iterative replanning | ✅ Live |
| Section synthesis & combination | ✅ Live |
| LaTeX composition (IEEE/ACM/Beamer/Poster) | ✅ Live |
| Citation verification & auto-fix | ✅ Live |
| Formula normalization & verification | ✅ Live |
| Hallucination guard | ✅ Live |
| Peer review automation | ✅ Live |
| Bias detection | ✅ Live |
| Knowledge graph construction | ✅ Live |
| Future work extrapolation | ✅ Live |
| Comparison table generation | ✅ Live |
| Figure generation (Mermaid/TikZ) | ✅ Live |
| Paper-to-Blog/Newsletter/Twitter export | ✅ Live |
| Interactive LaTeX preview | ✅ Live |
| Multi-paper survey generation | ✅ Live |
| Research Q&A chatbot (PDF library) | ✅ Live |
| Code execution & reproducibility | ✅ Live |
| Citation network visualization | ✅ Live |
| Dataset discovery (HF/Kaggle) | ✅ Live |
| Grant proposal generator | ✅ Live |
| Research trends dashboard | ✅ Live |
| Overleaf push/pull | ✅ Live |
| Plagiarism checker | ✅ Live |
| Voice intake | ✅ Live |
| Auth + session persistence | ✅ Live |
| WebSocket real-time streaming | ✅ Live |
| Watchdog literature monitoring | ✅ Live |

---

## Current Codebase Health

| Metric | Status | Details |
|--------|--------|---------|
| **Ruff lint** | ✅ PASS | 0 errors across 94 source files |
| **Mypy typecheck** | ⚠️ 8 errors | 3 low (optional deps), 4 medium, 1 high (config attr) |
| **Tests** | ⚠️ Partial | 95/97 pass in unit tests; 3 files hang (>30s timeout); 2 watchdog failures |
| **Coverage** | 🟡 Needs work | No integration tests with real graph execution through tools |

### Active Issues

Quick-fix priorities for the next maintenance sprint:

| Pri | Issue | File | Fix |
|-----|-------|------|-----|
| P0 | `_is_newer()` returns False for papers with no year (should assume recent) | `orchestration/watchdog.py` | Return True when year missing |
| P0 | Qdrant vector dimension mismatch — NVIDIA 1024d vs local 384d crashes upsert | `rag/indexer.py` | Detect dim change → recreate collection |
| P1 | `RetrievalSettings` missing `semantic_scholar_api_key` | `app/webapp.py:893` | Fix config attribute or use env var |
| P1 | `proposal_content` may be `None` sent to `write_text()` | `nodes/grant_proposal.py:68` | Add `or \"\"` fallback |
| P1 | Missing type stubs (fitz, pdfplumber, sentence_transformers) | 3 files | Add `# type: ignore[import-not-found]` |
| P2 | 3 test files hang (test_smoke, test_webapp, test_worker_node) | fixture/async | Investigate and fix |
| P2 | `code_execution.py` `run_warnings` typed as `object` | `nodes/code_execution.py:161` | Add explicit list cast |

---

## Implementation Phases

Each phase is ordered by value-to-effort ratio. Priority scores combine:
- **P0**: Critical for correctness/stability
- **P1**: High user value, feasible in 1-2 sprints
- **P2**: Medium value, requires deeper architecture work
- **P3**: Lower urgency, nice-to-have

---

## Phase 5: Intelligent Research Core (Current Sprint)

### P15 — Intelligent Research Assistant (Agentic Chat)
**Why:** Current Q&A is passive keyword retrieval. An agentic chat with tool-calling, cross-session memory, and proactive suggestions is a step-change in usefulness.

**What to build:**
- [ ] Tool-calling agent loop: user asks → agent decides which tools (search, citation check, dataset discovery, PDF analysis) → executes → synthesizes answer
- [ ] Cross-session memory store (Redis): recall past conversations, research context, user preferences
- [ ] Proactive suggestions engine: "Your paper on transformers is missing a comparison with Mamba. Search recent papers?"
- [ ] Research planning mode: "Write a survey on X" → agent decomposes into sub-topics → generates outline → researches each → compiles into full paper
- [ ] Integration with graph pipeline: `/api/chat/launch-research` kicks off full `run_graph` from chat context
- [ ] Streaming responses with citations rendered inline as the agent works
- [ ] User feedback buttons (helpful / not helpful) to fine-tune agent behavior per session

**Feasibility:** High. Leverages existing chat infra, worker pool, and tool registry. Primary work is prompt engineering + orchestration logic.

**Dependencies:** None
**Estimated effort:** 2-3 sprints
**Key files:** `chat/ask.py`, `orchestration/graph.py`, `app/webapp.py`

---

### P12 — AI Model Router & Multi-Provider Support
**Why:** Different LLMs excel at different tasks. A smart router selects the best model per task (planning vs writing vs math), provides fallback resilience, and tracks costs.

**What to build:**
- [ ] Model router YAML config: map task types (`plan`, `write`, `critique`, `code`, `embed`) to specific models per provider
- [ ] Provider adapters: OpenAI, Anthropic, Google Gemini, Ollama (local), Groq, NVIDIA NIM, OpenRouter
- [ ] Automatic fallback chain: primary → secondary → tertiary (e.g., GPT-4 → Claude → local Ollama)
- [ ] Cost tracking per model per run with budget enforcement (stop when `max_cost_usd` exceeded)
- [ ] Latency-aware routing: prefer fast models (Groq, Gemini Flash) for interactive/chat tasks; heavy models (GPT-4, Claude Opus) for composition
- [ ] Settings UI: user-configurable model preferences + API keys per provider
- [ ] Embedding provider support: OpenAI, NVIDIA, local sentence-transformers, with fallback chain
- [ ] Live `/api/health/models` endpoint showing availability of each configured model
- [ ] Deterministic fallback: when ALL LLMs unavailable, use template-based generation (already partially implemented)

**Feasibility:** Medium. Requires abstracting the current NVIDIA-centric `llm_client.py` into a multi-provider system with pluggable adapters.

**Dependencies:** Current `models/nvidia_client.py` and `models/llm_client.py` need refactoring
**Estimated effort:** 3-4 sprints
**Key files:** `models/llm_client.py`, `models/nvidia_client.py`, `config/schema.py`

---

### P13 — Automated Literature Monitoring & Alerting
**Why:** The watchdog subscription endpoints exist but are not wired to a scheduler. A daily/weekly digest of new papers keeps researchers current without manual checking.

**What to build:**
- [ ] Background scheduler (APScheduler): poll ArXiv + Semantic Scholar daily for subscribed topics
- [ ] True diff detection: compare paper fingerprints (title + author hash) against previously seen set to identify genuinely new papers
- [ ] Relevance scoring: rank new papers (0-1) against user's interest profile using embedding similarity
- [ ] Email digest generator: Markdown → HTML email with summaries, links, and relevance badges
- [ ] Dashboard widget: "Latest Papers" feed in sidebar showing recent discoveries per profile
- [ ] "One-click deep dive": from any discovered paper in the digest → launch full `run_graph` with that paper as context
- [ ] Rate limiting: respect ArXiv API rate limits (1 req/3s), stagger provider queries
- [ ] Notification preferences: per-profile push (in-app) or email, configurable frequency

**Feasibility:** Medium. Watchdog storage layer exists, endpoints exist, scheduler is the missing piece.

**Dependencies:** P16 (Job Queue) for production — APScheduler works for single-process
**Estimated effort:** 2 sprints
**Key files:** `orchestration/watchdog.py`, `app/watchdog_storage.py`, `app/webapp.py`

---

### P11 — Multi-User Collaborative Research Sessions
**Why:** Research is collaborative. Real-time co-editing with comments and role-based access makes this a true team platform.

**What to build:**
- [ ] Shared session model: invite collaborators by email, assign roles (lead, contributor, reviewer)
- [ ] CRDT-based real-time co-editing via WebSocket broadcast (Yjs integration)
- [ ] Per-section locking: prevent two users editing the same paragraph simultaneously
- [ ] Comment threads: highlight text → add comment → @mention collaborator → notification
- [ ] Cursor presence: see where other users are typing in real-time
- [ ] Version history: snapshot-based with diff viewer and rollback
- [ ] Activity feed: "Alice edited the methodology section" — who changed what, when
- [ ] Permission model: viewer / commenter / editor / admin
- [ ] Invite flow: share link → auto-register → join session

**Feasibility:** Medium-High. WebSocket infra exists. Yjs is mature. Primary work is frontend + session management.

**Dependencies:** Auth system already supports users
**Estimated effort:** 4-5 sprints
**Key files:** `app/webapp.py` (WebSocket), frontend JS, new `sessions.py` model

---

### P14 — Research Knowledge Graph Explorer
**Why:** Knowledge graphs exist per-run but are siloed. A cross-run persistent KG enables researchers to explore connections across all past research.

**What to build:**
- [ ] Persistent Neo4j graph store aggregating entities across all runs (concepts, methods, authors, datasets, results)
- [ ] Entity deduplication: merge same author, concept, or paper across runs using fuzzy matching + LLM verification
- [ ] Relationship inference: "X outperforms Y", "Z builds on X", "uses dataset D" — extracted via LLM + rule-based patterns
- [ ] Interactive graph explorer (WebGL-based, three.js or Sigma.js): zoom, pan, filter, click for details
- [ ] Semantic search over the KG: "find all papers connecting attention mechanisms to multimodal learning"
- [ ] Export subgraphs as SVG/PNG for inclusion in papers
- [ ] "Research landscape" view: entire body of user's research at a glance, colored by topic cluster
- [ ] Time-based animation: show how the research landscape evolved over months

**Feasibility:** Medium-High. Per-run KG extraction already exists in pipeline. Needs persistent store and aggregation layer.

**Dependencies:** None for Neo4j (Docker image). NetworkX is lighter alternative.
**Estimated effort:** 4-5 sprints
**Key files:** `orchestration/nodes/knowledge_graph.py` (rewrite), new `knowledge_graph/` module

---

## Phase 6: Production Hardening

### P16 — Async Job Queue & Worker Scaling
**Why:** In-process graph execution blocks the server. A distributed task queue enables concurrent research runs, cancellation, retry, and horizontal scaling.

**What to build:**
- [ ] Celery or RQ integration with Redis broker
- [ ] Job model: `run_id`, `status` (queued/running/completed/failed/cancelled), `progress`, `created_at`, `user_id`
- [ ] Progress streaming: Celery tasks push progress to Redis pub/sub → WebSocket bridge to frontend
- [ ] Job priority: interactive requests (priority 1) > background jobs (priority 2) > batch exports (priority 3)
- [ ] Cancellation: task checks `cancel_event` flag at each graph node boundary
- [ ] Dead letter queue: failed runs go to DLQ with error context for debugging
- [ ] Retry with backoff: transient failures (rate limits, timeouts) → auto-retry up to 3x with exponential backoff
- [ ] Worker auto-scaling with Kubernetes HPA based on queue depth
- [ ] Graceful shutdown: workers finish current node before terminating

**Feasibility:** Medium. LangGraph already supports checkpointing which maps naturally to job persistence.

**Dependencies:** Redis (already a dependency)
**Estimated effort:** 3-4 sprints
**Key files:** New `workers/` module, `orchestration/graph.py` refactor

---

### P17 — Comprehensive Observability Stack
**Why:** No visibility into pipeline performance, LLM costs, error rates, or bottlenecks means flying blind.

**What to build:**
- [ ] OpenTelemetry instrumentation on every graph node, LLM call, and tool adapter
- [ ] Prometheus metrics: request latency (histogram by node), LLM token usage (counter), error rate by node, queue depth, active runs
- [ ] Grafana dashboard templates: research pipeline overview, cost analytics, error breakdown
- [ ] Structured JSON logging with correlation IDs across full pipeline (run_id → task_id → node_id)
- [ ] Cost analytics dashboard: per-user, per-run, per-model token spend with budget alerts
- [ ] Performance tracing: flamegraph-style view of where time is spent in the pipeline
- [ ] Log level configuration per module without restart
- [ ] Metrics endpoint `GET /api/metrics` for Prometheus scraping

**Feasibility:** Medium. OpenTelemetry Python SDK is mature. Prometheus has a Python client.

**Dependencies:** P16 (Job Queue) provides the runtime model for metric collection
**Estimated effort:** 2-3 sprints
**Key files:** New `observability/otel.py`, `observability/metrics.py`

---

### P18 — Security Hardening & Enterprise Features
**Why:** Production deployments need rate limiting, injection defense, audit logs, and enterprise auth.

**What to build:**
- [ ] Rate limiting per endpoint per user (slowapi or custom middleware): 10 req/s for chat, 2 req/s for research runs
- [ ] Prompt injection defense: input sanitization (strip control chars, truncate), output guardrails (block harmful content patterns)
- [ ] Audit logging: who accessed what data, when, with request/response summary (structured JSON)
- [ ] SSO/SAML/OIDC integration for enterprise deployments (Auth0, Okta, Azure AD)
- [ ] Data retention policies: configurable TTL for run artifacts, chat uploads, session data
- [ ] GDPR compliance tooling: user data export (`GET /api/user/export`), account deletion (`DELETE /api/user`)
- [ ] RBAC: viewer (see runs) / researcher (run graphs) / admin (manage users, settings) roles
- [ ] API key authentication for programmatic access (in addition to JWT)

**Feasibility:** Medium. Auth layer exists via fastapi-users. Rate limiting is a middleware add.

**Dependencies:** None
**Estimated effort:** 3-4 sprints

---

### P19 — Plugin & Extension System
**Why:** Allow community and enterprise users to extend the agent without modifying core code.

**What to build:**
- [ ] Plugin API: register new graph nodes via Python entry points (`pyproject.toml [project.entry-points."research_agent.nodes"]`)
- [ ] Hook system: `before_node`, `after_node`, `on_error` hooks for custom processing
- [ ] Custom tool adapters: user-defined search sources (Google Scholar, DBLP, Crossref, PubMed Central)
- [ ] Template marketplace: community-contributed LaTeX templates registered via plugin
- [ ] Export plugins: custom output formats (Word .docx, EPUB, AsciiDoc, HTML, Jupyter Book)
- [ ] Plugin discovery: `GET /api/plugins` lists installed plugins with version and metadata
- [ ] Sandbox plugin execution: plugins run in isolated subprocess with limited resource access

**Feasibility:** Medium. Python entry points provide natural plugin discovery. Template rendering is already modular.

**Dependencies:** None
**Estimated effort:** 3 sprints

---

### P20 — Mobile & Offline Support
**Why:** Researchers work across devices. Offline mode with local LLMs enables research anywhere.

**What to build:**
- [ ] Progressive Web App (PWA): service worker for offline caching of generated papers and artifacts
- [ ] Responsive mobile-first UI redesign: collapsible sidebar, touch-friendly buttons, swipe actions
- [ ] Background sync: queue research requests offline, execute when connectivity restored
- [ ] Push notifications for long-running research completion (Web Push API)
- [ ] Local-first mode: run with Ollama (local LLM) for fully offline research
- [ ] Offline artifact viewer: browse generated PDFs, LaTeX, and reports without internet
- [ ] Sync conflict resolution: when coming back online, merge offline edits with server state

**Feasibility:** Medium-High. PWA is frontend work. Ollama integration depends on P12 (Model Router).

**Dependencies:** P12 (Ollama support in Model Router), P16 (Background jobs)
**Estimated effort:** 4-5 sprints

---

## Phase 7: Agentic RAG & Multi-Modal Intelligence

### P21 — Agentic Deep Research Engine
**Why:** Current research executes a single linear pass. Modern systems (ChatGPT Deep Research, STORM 2.0) use iterative, self-correcting search loops for dramatically better results.

**What to build:**
- [ ] **Iterative query refinement loop**: after initial search, analyze coverage gaps → generate follow-up queries → re-search
- [ ] **Self-reflection scorer**: score retrieved evidence on relevance, recency, authority → decide if deeper search needed
- [ ] **Multi-perspective routing**: route the same question to keyword search, semantic search, citation-traversal, and dataset search → merge results
- [ ] **Configurable depth**: "quick" (1 pass, 30s), "balanced" (2-3 passes, 2min), "deep" (5+ passes with citation chaining, 5min)
- [ ] **Progress streaming per iteration**: user sees real-time "Searching for X... Found Y results. Identifying gaps... Searching for Z..."
- [ ] **Citation chaining**: take top papers from pass 1, follow their references → pass 2, follow who cited them → pass 3
- [ ] **Contradiction detection across passes**: flag when different sources make conflicting claims; include both in output

**Feasibility:** Medium. Builds on existing worker pool and critic loop. The `planner.py` node already decomposes topics — extending it for iterative refinement is natural.

**Dependencies:** P15 (Agentic Chat) can reuse the same orchestration patterns
**Estimated effort:** 4-5 sprints
**Key files:** New `orchestration/nodes/deep_search.py`, `orchestration/nodes/query_refiner.py`

---

### P22 — Multi-Modal Paper Analysis (Figures, Tables, Equations)
**Why:** Research papers contain critical information in figures, tables, and equations — not just text. Multi-modal RAG treats every element as a first-class citizen.

**What to build:**
- [ ] **Figure extraction**: use PyMuPDF to extract images from PDFs with their captions
- [ ] **Table extraction**: detect and parse tables (tabulate, camelot, or PyMuPDF table extraction)
- [ ] **Equation extraction**: regex-detect math environments (`\begin{equation}...\end{equation}`), store as LaTeX + rendered PNG
- [ ] **Multi-modal embedding**: embed figures via vision encoder (CLIP or SigLIP), tables via table-specific encoder (TAPAS), text via text encoder
- [ ] **Unified Qdrant index**: all modalities share a single collection with vector-size tags for filtering
- [ ] **Inline rendering in answers**: "Figure 3 shows the architecture..." with thumbnail display in chat
- [ ] **Table-aware Q&A**: retrieve specific cells/rows, not whole tables — "What was the F1 score in Table 2 for the BERT model?"
- [ ] **Equation-aware Q&A**: retrieve specific equations by number + concept — "What is the loss function (Eq 5) in the transformer paper?"

**Feasibility:** Medium-High. Requires vision embedding model. Qdrant supports heterogeneous vectors. The `rag/table_extractor.py` module already exists as a stub.

**Dependencies:** P26 (Personal Library) for the PDF ingestion pipeline
**Estimated effort:** 5-6 sprints
**Key files:** `rag/table_extractor.py` (upgrade), new `rag/multimodal_embedder.py`, `rag/figure_extractor.py`

---

### P23 — GraphRAG Knowledge Graph Retrieval
**Why:** Current RAG uses flat text chunks. GraphRAG builds entity-relationship knowledge graphs for multi-hop reasoning and global summarization — dramatically better for complex research queries.

**What to build:**
- [ ] **Entity extraction pipeline**: extract named entities from paper chunks (techniques, algorithms, datasets, metrics, authors, institutions) using LLM + spaCy
- [ ] **Relationship extraction**: build typed edges between entities ("X outperforms Y", "Z_builds_on_X", "uses_dataset_D", "trains_on_D")
- [ ] **Persistent Neo4j store**: aggregate entities and relationships across ALL runs (not just per-run)
- [ ] **Graph-enhanced retrieval**: given a query, extract entities → traverse KG to find relevant entities + their source papers + relationships
- [ ] **Cross-run entity resolution**: merge same entity across different research runs (fuzzy name matching + LLM verification)
- [ ] **Global summarization**: use graph community detection (Louvain/Leiden) to find topic clusters → generate overview per cluster
- [ ] **Local graph exploration**: for a single paper, show its entity neighborhood — "What methods does this paper build on? What later work builds on it?"
- [ ] **Time-aware graph**: show how entities and relationships evolved over time (e.g., "attention mechanisms" → "self-attention" → "sparse attention")

**Feasibility:** Medium. Per-run KG extraction already exists. NetworkX is sufficient for MVP; Neo4j for production.

**Dependencies:** P14 is the same feature in Phase 5. Consider merging timelines.
**Estimated effort:** 5-6 sprints
**Key files:** New `knowledge_graph/` module, `orchestration/nodes/knowledge_graph.py` rewrite

---

### P24 — Verified Code Execution Sandbox
**Why:** `code_execution.py` runs extracted code directly on the host — a security and reproducibility risk. An isolated sandbox makes it safe and deterministic.

**What to build:**
- [ ] Docker sandbox: auto-build minimal Python image with common scientific packages (numpy, scipy, sklearn, torch, matplotlib)
- [ ] File system isolation: write `.py` script to temp dir → mount read-only → capture stdout/stderr → timeout 30s → cleanup
- [ ] Result verification: compare numerical outputs against paper claims with truncation-aware comparison (tolerance = 1e-4)
- [ ] Resource limits: CPU quota (0.5 cores), memory cap (512MB), network disabled
- [ ] Jupyter kernel integration: spawn real IPython kernel for notebook execution instead of script-based
- [ ] Claim extraction: parse paper for numerical claims ("our model achieves 92.3% accuracy") → match against execution output
- [ ] Claim verification matrix: verified / refuted / unverifiable — with evidence links
- [ ] Integration test: mock paper with known numerical result → verify sandbox produces matching output

**Feasibility:** Medium. Docker is heavy for CI. Start with `subprocess` in ephemeral temp dirs + timeouts. Docker as optional.

**Dependencies:** Existing `code_execution.py` node
**Estimated effort:** 3-4 sprints
**Key files:** `orchestration/nodes/code_execution.py` (rewrite), new `verification/sandbox.py`

---

## Phase 8: Human-Centric Collaboration & UX

### P25 — Collaborative Real-Time Co-Editing
**Why:** Research is collaborative. Multiple researchers working on the same paper with real-time sync and conflict resolution is the biggest UX differentiator.

**What to build:**
- [ ] CRDT sync via Yjs: every keystroke synced across collaborators using y-py (Python Yjs binding) or y-websocket bridge
- [ ] WebSocket sync layer: extends existing `/ws/chat/{session_id}` with document sync messages
- [ ] Section-level locking: lock a section when a user starts editing → prevent simultaneous edits
- [ ] Comment threads: highlight text → add comment → @mention collaborator → notification
- [ ] Cursor presence: see where other users are typing in real-time (colored cursors + names)
- [ ] Version history: auto-snapshot on every 5-minute idle → diff viewer with rollback
- [ ] Role-based access: viewer (read-only) / commenter (add comments) / editor (edit sections) / admin (manage permissions)
- [ ] Activity sidebar: chronological feed of "Alice edited Methodology", "Bob added a comment on Results"
- [ ] Export with collaboration metadata: LaTeX comments track authorship per section

**Feasibility:** High. WebSocket infra exists. Yjs is mature with Python bindings available. Primary work is frontend.

**Dependencies:** Auth system for role management
**Estimated effort:** 5-6 sprints
**Key files:** `app/webapp.py` (WebSocket upgrade), new frontend `collab/` module

---

### P27 — Multi-Format Paper Submission Pipeline
**Why:** Researchers submit to multiple venues with different formatting. Auto-converting between IEEE, ACM, Springer, AAAI saves hours and prevents formatting rejections.

**What to build:**
- [ ] **Template converter**: take generated LaTeX in one format → reflow into another — IEEE ↔ ACM ↔ Springer ↔ AAAI
- [ ] **Page limit enforcement**: auto-detect overflow → selectively shrink (compress figures, tighten prose, reduce bibliography font)
- [ ] **Venue-specific checklist**: anonymization check (remove author names), page count, section structure requirements, conflict-of-interest statements
- [ ] **Cover letter generator**: auto-generate submission cover letter from paper + venue guidelines
- [ ] **Conference API integration**: auto-submit to HotCRP, EasyChair, OpenReview via their APIs
- [ ] **Format validation pre-check**: catch formatting errors before human review — missing sections, incorrect margins, wrong font sizes
- [ ] **Submission history**: track which papers were submitted to which venues, with dates and outcomes

**Feasibility:** Medium. Template infrastructure exists. LaTeX→LaTeX conversion is deterministic (regex + Jinja2). API integrations are new work.

**Dependencies:** Existing `output/latex/templates/` provides the foundation
**Estimated effort:** 3-4 sprints
**Key files:** New `output/submission/` module, `output/latex/renderer.py` upgrade

---

### P28 — Personal Research Library with Smart Organization
**Why:** Users accumulate papers across runs. A personal library with auto-tagging, similarity grouping, and smart search makes past research findable and reusable.

**What to build:**
- [ ] **Library import**: upload PDFs via drag-and-drop, or import from Zotero/Mendeley/Paperpile via their OAuth APIs
- [ ] **Auto-tagging**: extract key concepts, methods, datasets from each paper → generate hierarchical tags (method:transformer, dataset:squad)
- [ ] **Similarity grouping**: cluster papers by embedding similarity → show "Papers like this" on every paper page
- [ ] **Full-text search**: search across ALL papers using existing Qdrant index with faceted filters (by year, author, tag, venue)
- [ ] **Reading list management**: statuses (to-read, in-progress, read) with custom lists
- [ ] **Citation export**: one-click copy BibTeX/CSL/RIS for selected papers
- [ ] **Paper detail view**: title, authors, abstract, tags, similar papers, and "Run research on this topic" button
- [ ] **Integration**: one-click "Research this topic" → launches full `run_graph` with paper as context
- [ ] **PDF viewer**: in-browser PDF viewer with highlight + annotation support

**Feasibility:** Medium. Reuses Qdrant + chunker/parser infrastructure. Zotero API is well-documented.

**Dependencies:** P22 (Multi-Modal) for PDF figure/table extraction
**Estimated effort:** 4-5 sprints
**Key files:** New `library/` module, `chat/ask.py` upgrade

---

### P29 — Reproducibility Dashboard & Experiment Tracking
**Why:** Researchers need to track which code ran successfully, what results were produced, and whether claims are verified. A dashboard makes this visible and actionable.

**What to build:**
- [ ] **Run history table**: for each code execution → status (pass/fail/timeout), duration, output preview, paper reference
- [ ] **Claim verification matrix**: paper claims extracted → matched against execution output → verified / refuted / unverifiable
- [ ] **Per-execution environment snapshot**: OS, Python version, all package versions, GPU info (nvidia-smi), CPU info
- [ ] **Export executable artifact**: bundle `.py` + `requirements.txt` + README with instructions
- [ ] **Comparison mode**: side-by-side view of two runs — "Did the results change between these two code versions?"
- [ ] **Regression detection**: if a paper's claimed numbers differ from execution output, flag as possible regression
- [ ] **Integration**: dashboard tab in web UI showing all executions for a run, linked from the run results page

**Feasibility:** Medium. Code execution node exists (`code_execution.py`). Dashboard is primarily frontend work.

**Dependencies:** P24 (Verified Sandbox) for safe execution
**Estimated effort:** 2-3 sprints
**Key files:** `orchestration/nodes/code_execution.py`, new `app/web/reproducibility/` frontend

---

### P26 — AI Research Assistant (Agentic Chat with Memory)
*Note: This is P15 in Phase 5. Adding here the more advanced version.*

**Why:** The basic agentic chat is Phase 5. This Phase 8 version adds autonomous workflow execution, multi-session orchestration, and deep integration with the full pipeline.

**Additional advanced capabilities:**
- [ ] Autonomous research mode: user says "Compare methods for protein folding prediction" → agent orchestrates full multi-paper survey + code verification + gap analysis automatically
- [ ] Multi-session orchestration: agent runs multiple research sessions in parallel, merges results into a single coherent output
- [ ] Deep memory: agent remembers user's research interests, past papers, frequently used methodologies across months of interaction
- [ ] Hypothesis generation: agent proposes novel hypotheses based on cross-paper analysis and literature gaps
- [ ] Experiment design assistant: given a hypothesis, agent designs experiments, suggests controls, estimates sample sizes
- [ ] Automated rebuttal generation: for peer review feedback, agent generates point-by-point rebuttals with citations
- [ ] Citation graph-aware chat: "Find papers that cite both the Transformer paper and the Mamba paper" — traverses the cross-run knowledge graph

**Feasibility:** Medium. Builds on Phase 5's P15 and Phase 7's P21 + P23.

**Dependencies:** P15 (basic agentic chat), P23 (GraphRAG for citation-aware answers)
**Estimated effort:** 5-6 sprints

---

## Phase 9: Production Infrastructure

| # | Feature | Effort | Dependencies | Key Value |
|---|---------|--------|-------------|-----------|
| P30 | **Async Job Queue** (Celery/RQ + K8s HPA) | 3-4 sprints | Redis | Unlocks concurrency & scaling |
| P31 | **Observability Stack** (OTel + Prometheus + Grafana) | 2-3 sprints | P30 | Operational visibility |
| P32 | **Security Hardening** (RBAC, SSO, rate limiting) | 3-4 sprints | Auth system | Enterprise readiness |
| P33 | **Plugin System** (entry points + hooks) | 3 sprints | None | Extensibility & community |

---

## Phase 10: Cutting-Edge Research Features

### P34 — Multi-Agent Research Swarm
**Why:** Different research perspectives (theorist, experimentalist, critic) can collaborate within a single run — an approach pioneered by Agent Laboratory and STORM.

**What to build:**
- [ ] Role-based agents: TheoristAgent (conceptual background), ExperimentalistAgent (methods/results), CriticAgent (bias/rigor check), EditorAgent (synthesis/writing)
- [ ] Debate protocol: agents take positions, debate findings, then converge on consensus
- [ ] Parallel research branches: theorist explores background while experimentalist searches for datasets concurrently
- [ ] Peer review loop between agents: CriticAgent reviews TheoristAgent's output → gives feedback → revision
- [ ] Configurable swarm size: 2 agents (minimal) to 7+ agents (comprehensive)
- [ ] Visualization: real-time view of what each agent is doing in the swarm

**Feasibility:** Medium. Existing worker pool provides the substrate. New orchestration protocol needed.

---

### P35 — Cross-Lingual Research & Translation
**Why:** Research is global. Papers in Chinese, Japanese, German, French, Spanish contain valuable findings that English-only searches miss.

**What to build:**
- [ ] Query translation: translate user's English query → search non-English sources (CNKI, J-Stage, PubMed non-English)
- [ ] Cross-lingual embeddings: use multilingual embedding model (intfloat/multilingual-e5-large) for language-agnostic retrieval
- [ ] Answer translation: generate final paper in user's preferred language while preserving citations
- [ ] Language detection: auto-detect source language and route to appropriate providers
- [ ] Multi-lingual LaTeX: generate LaTeX with proper babel/polyglossia packages for non-English documents

**Feasibility:** Medium. Multilingual embedding models are mature. Translation APIs are well-documented.

---

### P36 — Paper-git: Version Control for Research Artifacts
**Why:** Researchers iterate on papers with multiple versions, co-authors, and experiments. Git-like versioning for research artifacts enables history, branching, and merging.

**What to build:**
- [ ] Snapshot model: every `run_graph` execution creates an immutable snapshot of all artifacts (tex, bib, figures, summary.json)
- [ ] Diff viewer: side-by-side comparison of two snapshots — visual LaTeX diff, citation changes, figure changes
- [ ] Branching: create a branch to explore an alternative methodology, merge back
- [ ] Collaboration graph: see who made what changes across the history
- [ ] Rollback: revert to any previous snapshot with one click
- [ ] API: `GET /api/runs/{run_id}/history` → list of snapshots with timestamps and authors
- [ ] Git integration: auto-commit artifacts to a Git repository for external collaboration

**Feasibility:** High. Checkpoint system already saves state at each node boundary. Extending to a full version history is natural.

---

### P37 — Automated Peer Review with Confidence Scoring
**Why:** Beyond generating a peer review report (already done), this feature assigns confidence scores to each review point and generates a review summary card suitable for conference reviewing systems.

**What to build:**
- [ ] Structured review output: scores for novelty, clarity, methodology, reproducibility, significance (each 1-10)
- [ ] Confidence intervals: per-score confidence based on how well-supported the review claim is (high/medium/low)
- [ ] Review summary card: one-page PDF formatted as a conference review form
- [ ] Rebuttal preview: given a review, generate suggested author responses with supporting citations
- [ ] Multi-reviewer simulation: generate 3 independent reviews from different simulated reviewer personas (strict, generous, methodology-focused)
- [ ] Meta-review synthesis: take 3 reviews → generate a meta-review with decision recommendation

**Feasibility:** High. `peer_reviewer.py` node already exists. This adds structure and formatting around existing output.

---

### P38 — Interactive Tutorial & Onboarding System
**Why:** New users face a steep learning curve with the research agent's many features. An interactive tutorial makes onboarding smooth.

**What to build:**
- [ ] Guided walkthrough: step-by-step tutorial that runs a mini research session with explanations at each stage
- [ ] Command palette: `Ctrl+K` / `Cmd+K` searchable command palette for all actions
- [ ] Contextual help: "?" buttons next to each UI element with tooltip explanations
- [ ] Sample topics: pre-seeded sample research topics with one-click "Run this" buttons
- [ ] Feature discovery: highlight newly available features with badges and "What's new" modal
- [ ] Keyboard shortcuts guide: press `?` to show all available keyboard shortcuts

**Feasibility:** High. Frontend-only work. No new infrastructure needed.

---

## Strategic Sequencing

This sequencing maximizes value delivery by prioritizing features that unblock other features:

```
Sprint 1-2 (NOW):  Fix bugs → P15 Agentic Chat (basic) → P12 Model Router
Sprint 3-4:        P13 Literature Monitoring → P21 Deep Research Engine
Sprint 5-6:        P24 Code Sandbox → P16 Job Queue → P17 Observability
Sprint 7-8:        P22 Multi-Modal → P23 GraphRAG → P28 Personal Library
Sprint 9-10:       P25 Co-Editing → P27 Submission Pipeline → P18 Security
Sprint 11+:        P26 Advanced Agentic → P34 Swarm → P36 Paper-git
```

### First-Mover Advantage Features

These features would differentiate this project from every other open-source research agent:

1. **P24 Verified Code Sandbox** — No other tool (Elicit, Scite, STORM) verifies paper claims by executing code
2. **P22 Multi-Modal RAG** — Figure/table/equation understanding is the next frontier in paper analysis
3. **P23 GraphRAG** — Cross-run knowledge graphs are unique; most tools are single-session only
4. **P36 Paper-git** — Research artifact versioning is an unmet need in the academic AI space
