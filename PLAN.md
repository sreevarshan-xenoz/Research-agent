# Research Agent v2 — Strategic Roadmap

> **Last updated:** July 2, 2026
> **Status:** Active development — 30+ pipeline nodes, 8 integrated services, full research lifecycle automated
> **Research sources:** STORM, GPT-Researcher, Agent Laboratory, AI-Researcher, Elicit, Scite, Consensus, NotebookLM, GraphRAG, MG²-RAG, MiA-RAG

---

## Current Capabilities

The project delivers a complete research lifecycle pipeline with all 30+ features live:

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
| **Mypy typecheck** | ✅ PASS | 0 errors across 94 source files |
| **Tests (core)** | ✅ PASS | All unit tests passing (31 tests) |
| **Tests (graph)** | 🟡 Skipped | 3 test files need mock-based async fixture fix. Tracked in conftest.py |
| **Coverage** | 🟡 Needs work | No integration tests with real graph execution through tools |

---

## Implementation Phases

Each phase is ordered by value-to-effort ratio.

---

## Phase 5: Intelligent Research Core (Current Sprint)

### P15 — Intelligent Research Assistant (Agentic Chat) ⬅️ ACTIVE
**Why:** Current Q&A is passive keyword retrieval. An agentic chat with tool-calling, cross-session memory, and proactive suggestions is a step-change in usefulness.

**What to build:**
- [x] Chat API endpoints (`/api/chat/upload`, `/api/chat/ask`, `/api/chat/library`)
- [x] PDF parser, chunker, indexer, and ask modules
- [x] **Tool-calling agent loop** (`chat/agent.py`): agent decides tools → executes → synthesizes answer with citations
- [x] **Cross-session memory store** (`chat/memory.py`): InMemoryMemoryStore + RedisMemoryStore fallback
- [x] **Proactive suggestions engine**: `/api/chat/suggestions` + `_generate_suggestions()` in webapp.py
- [x] **Integration with graph pipeline**: `/api/chat/launch-research` kicks off full `run_graph` from chat context
- [x] **Streaming agentic chat**: `/api/chat/agent/stream` with NDJSON events (thought, tool_call, token, complete)
- [x] **Agentic chat API**: `/api/chat/agent` endpoint with tool-calling loop, citations, and suggestions
- [x] **Memory API**: `/api/chat/memory` for storing/retrieving user preferences and research context
- [x] **Research planning mode**: /api/chat/plan endpoint + plan panel in composer + research intent detection in JS
- [x] **User feedback buttons**: /api/chat/feedback endpoint + thumbs up/down on every assistant message
- [x] **Frontend chat UI**: Agent chat panel with streaming, suggestions, citations, plan display, and feedback

**Feasibility:** High. Leverages existing chat infra, worker pool, and tool registry.
**Estimated effort:** 2-3 sprints
**Key files:** `chat/ask.py`, `orchestration/graph.py`, `app/webapp.py`

---

### P12 — AI Model Router & Multi-Provider Support
**Why:** Different LLMs excel at different tasks. A smart router selects the best model per task, provides fallback resilience, and tracks costs.

**What to build:**
- [x] Provider adapters: Ollama, OpenRouter, NVIDIA, vLLM
- [x] Automatic fallback chain (provider_priority config)
- [x] Deterministic fallback when all LLMs unavailable
- [x] LiteLLM unified client with streaming support
- [ ] **Model router YAML config**: map task types (`plan`, `write`, `critique`, `code`, `embed`) to specific models per provider
- [ ] **Provider adapters**: OpenAI, Anthropic, Google Gemini, Groq
- [ ] **Cost tracking** per model per run with budget enforcement
- [ ] **Latency-aware routing**: prefer fast models for interactive tasks
- [ ] **Settings UI**: user-configurable model preferences + API keys per provider
- [ ] **Embedding provider support**: OpenAI, NVIDIA, local sentence-transformers, with fallback chain
- [ ] **Live `/api/health/models` endpoint** showing availability of each configured model

**Feasibility:** Medium. Core multi-provider architecture exists in `llm_client.py`.
**Estimated effort:** 2-3 sprints
**Key files:** `models/llm_client.py`, `config/schema.py`

---

### P13 — Automated Literature Monitoring & Alerting
**Why:** Watchdog subscription endpoints exist but are not wired to a scheduler.

**What to build:**
- [x] Watchdog subscription CRUD endpoints (`/api/watchdog/subscribe`, `/api/watchdog/subscriptions`, `/api/watchdog/subscriptions/{id}`)
- [x] Watchdog digest storage and formatting
- [x] Manual check endpoint (`/api/watchdog/check`)
- [ ] **Background scheduler** (APScheduler): poll ArXiv + Semantic Scholar daily for subscribed topics
- [ ] **True diff detection**: compare paper fingerprints against previously seen set
- [ ] **Relevance scoring**: rank new papers (0-1) against user's interest profile
- [ ] **Email digest generator**: Markdown → HTML email with summaries and links
- [ ] **Dashboard widget**: "Latest Papers" feed in sidebar
- [ ] **"One-click deep dive"**: launch full `run_graph` from a discovered paper
- [ ] **Notification preferences**: per-profile push or email, configurable frequency

**Feasibility:** Medium. Watchdog storage and endpoints exist.
**Estimated effort:** 2 sprints
**Key files:** `orchestration/watchdog.py`, `app/watchdog_storage.py`

---

### P11 — Multi-User Collaborative Research Sessions
**Why:** Real-time co-editing with comments and role-based access.

**Key components needed:**
- CRDT-based real-time co-editing via WebSocket (Yjs)
- Per-section locking, comment threads, cursor presence
- Version history with diff viewer and rollback
- Role-based access (viewer/commenter/editor/admin)

**Feasibility:** Medium-High. WebSocket infra exists. Yjs is mature.
**Estimated effort:** 4-5 sprints

---

### P14 — Research Knowledge Graph Explorer
**Why:** Cross-run persistent KG enables connection exploration across all past research.

**Key components needed:**
- Persistent Neo4j/NetworkX graph store
- Entity deduplication across runs
- Interactive graph explorer (three.js or Sigma.js)
- Semantic search over the KG
- Time-based animation of research landscape evolution

**Feasibility:** Medium-High. Per-run KG extraction already exists.
**Estimated effort:** 4-5 sprints

---

## Phase 6: Production Hardening

| # | Feature | Effort | Dependencies | Key Value |
|---|---------|--------|-------------|-----------|
| P16 | **Async Job Queue** (Celery/RQ + K8s HPA) | 3-4 sprints | Redis | Unlocks concurrency & scaling |
| P17 | **Observability Stack** (OTel + Prometheus + Grafana) | 2-3 sprints | P16 | Operational visibility |
| P18 | **Security Hardening** (RBAC, SSO, rate limiting) | 3-4 sprints | Auth system | Enterprise readiness |
| P19 | **Plugin System** (entry points + hooks) | 3 sprints | None | Extensibility & community |
| P20 | **Mobile & Offline Support** (PWA, local-first) | 4-5 sprints | P12, P16 | Cross-device research |

---

## Phase 7: Agentic RAG & Multi-Modal Intelligence

| # | Feature | Effort | Key Differentiator |
|---|---------|--------|-------------------|
| P21 | **Agentic Deep Research Engine** (iterative query refinement, citation chaining) | 4-5 sprints | Self-correcting search loops |
| P22 | **Multi-Modal Paper Analysis** (figures, tables, equations) | 5-6 sprints | Table-aware Q&A |
| P23 | **GraphRAG Knowledge Graph Retrieval** (entity extraction, cross-run resolution) | 5-6 sprints | Multi-hop reasoning |
| P24 | **Verified Code Execution Sandbox** (Docker, claim verification) | 3-4 sprints | ⭐ Unique differentiator |

---

## Phase 8: Human-Centric Collaboration & UX

| # | Feature | Effort |
|---|---------|--------|
| P25 | **Collaborative Real-Time Co-Editing** (Yjs, CRDT) | 5-6 sprints |
| P27 | **Multi-Format Paper Submission Pipeline** (IEEE↔ACM↔Springer) | 3-4 sprints |
| P28 | **Personal Research Library** (Zotero import, auto-tagging) | 4-5 sprints |
| P29 | **Reproducibility Dashboard** (experiment tracking) | 2-3 sprints |
| P26 | **Advanced AI Research Assistant** (autonomous mode, hypothesis generation) | 5-6 sprints |

---

## Phase 9: Production Infrastructure

| # | Feature | Effort | Dependencies |
|---|---------|--------|-------------|
| P30 | **Async Job Queue** (Celery/RQ + K8s HPA) | 3-4 sprints | Redis |
| P31 | **Observability Stack** (OTel + Prometheus + Grafana) | 2-3 sprints | P30 |
| P32 | **Security Hardening** (RBAC, SSO, rate limiting) | 3-4 sprints | Auth system |
| P33 | **Plugin System** (entry points + hooks) | 3 sprints | None |

---

## Phase 10: Cutting-Edge Research Features

| # | Feature | Effort |
|---|---------|--------|
| P34 | **Multi-Agent Research Swarm** (Theorist, Experimentalist, Critic, Editor) | 5-6 sprints |
| P35 | **Cross-Lingual Research & Translation** (multilingual embeddings) | 4-5 sprints |
| P36 | **Paper-git: Version Control for Research Artifacts** | 3-4 sprints |
| P37 | **Automated Peer Review with Confidence Scoring** | 2-3 sprints |
| P38 | **Interactive Tutorial & Onboarding System** | 2-3 sprints |

---

## Strategic Sequencing

```
Sprint 1-2 (NOW):  P15 Agentic Chat (tool-calling loop) → P12 Model Router (more providers + cost tracking)
Sprint 3-4:        P13 Literature Monitoring (scheduler) → P21 Deep Research Engine
Sprint 5-6:        P24 Code Sandbox → P16 Job Queue → P17 Observability
Sprint 7-8:        P22 Multi-Modal → P23 GraphRAG → P28 Personal Library
Sprint 9-10:       P25 Co-Editing → P27 Submission Pipeline → P18 Security
Sprint 11+:        P26 Advanced Agentic → P34 Swarm → P36 Paper-git
```

### First-Mover Advantage Features

1. **P24 Verified Code Sandbox** — No other tool verifies paper claims by executing code
2. **P22 Multi-Modal RAG** — Figure/table/equation understanding is the next frontier
3. **P23 GraphRAG** — Cross-run knowledge graphs are unique
4. **P36 Paper-git** — Research artifact versioning is an unmet need
