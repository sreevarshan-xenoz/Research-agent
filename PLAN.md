# Research Agent v2 — Feature Enhancement Plan

> Generated: May 2026
> Based on codebase analysis, user goals, and web research into cutting-edge academic research agent tools (STORM, GPT-Researcher, Agent Laboratory, AI-Researcher, Elicit, Scite).

---

## Current State Summary

The project already has a **sophisticated pipeline** covering the full research lifecycle:

| Phase | Current Status |
|-------|---------------|
| Intake + Clarification | ✅ Done |
| Planning + Worker Execution | ✅ Done |
| Deep RAG (Qdrant) Indexing | ✅ Done |
| Critic + Replanning | ✅ Done |
| Combination + Synthesis | ✅ Done |
| Knowledge Graph Construction | ✅ Done |
| Bias Detection | ✅ Done |
| Future Work Extrapolation | ✅ Done |
| Comparison Table Generation | ✅ Done |
| Figure Generation (Mermaid/TikZ) | ✅ Done |
| Citation Verification + Auto-fix | ✅ Done |
| LaTeX Composition (IEEE/ACM/Springer) | ✅ Done |
| Formula Normalization + Verification | ✅ Done |
| Hallucination Guard | ✅ Done |
| Peer Review Automation | ✅ Done |
| Presentation (Beamer) Generation | ✅ Done |
| Poster Generation | ✅ Done |
| Voice Intake | ✅ Done |
| Auth + Session Persistence | ✅ Done |
| WebSocket Real-time Updates | ✅ Done |

**Identified Gaps** — features that differentiate, have high user value, and are feasible for open-source:

---

## Priority 1: Interactive LaTeX Preview (P0 — High Differentiation, High Value)

**Why:** Currently users must download and compile `.tex` files locally. An in-browser rendered preview makes the app feel complete and professional — users see the paper instantly after generation.

**What to build:**
- [x] Serve compiled PDF via LaTeX rendering in Docker/tectonic
- [x] Or use client-side `\KaTeX` / `mathjax` for formula rendering + structural approximation
- [x] Display side-by-side: raw LaTeX ↔ rendered preview in the web UI
- [x] Update Gradio and FastAPI web apps with preview tabs

**Feasibility:** Medium. Requires Docker/tectonic server-side, or a good client-side approximation.

---

## Priority 2: Paper-to-Blog / Newsletter Generator (P0 — High Value, High Differentiation)

**Why:** Researchers want to disseminate findings beyond academic papers — to blogs, newsletters, Twitter threads. This turns the agent from a "paper factory" into a "research communication platform."

**What to build:**
- [x] New node `blog_generator.py` that takes `latex_main` + `peer_review_report` and generates:
  - Blog post (Markdown, SEO-optimized)
  - Newsletter summary (1-2 paragraphs)
  - Twitter/X thread (5-10 tweets)
- [x] Controls in UI: select output format
- [x] Export as markdown file in artifacts


**Feasibility:** Very high. Single LLM call + some templating. No new infrastructure.

---

## Priority 3: Multi-Paper Survey Generator (P1 — High Value, Medium Complexity)

**Why:** Researchers spend weeks writing survey papers. The agent can search across multiple topics and generate a synthesized survey with cross-referencing.

**What to build:**
- [x] New `survey_planner.py` node — accepts multiple topics or a broad area
- [x] Parallel search across topics using existing tool adapters
- [x] Cross-paper comparison and contradiction detection (reuse existing logic)
- [x] Generate survey paper with taxonomy table, timeline, and research landscape
- [x] Extend `comparison_table_node` to handle >5 references with better formatting

**Feasibility:** Medium. Reuses worker pool, indexing, combiner. New planner logic needed.

---

## Priority 4: Research Q&A Chatbot over Personal Library (P1 — High Value, Medium Complexity)

**Why:** Users want to upload papers (PDFs) and ask questions over them, RAG-style, without starting a full research run.

**What to build:**
- [x] Upload PDF endpoint → parse with PyMuPDF (already a dependency)
- [x] Store in Qdrant (reuse existing index infrastructure)
- [x] New `ask.py` endpoint: accept question + query Qdrant → LLM answer with citations
- [x] Web UI: chat interface over library
- [x] Support for multiple PDFs, cross-document queries


**Feasibility:** Medium. Adds new endpoint but reuses Qdrant + LLM infrastructure heavily.

---

## Priority 5: Code Execution & Reproducibility Verification (P1 — Medium Value, High Differentiation)

**Why:** Generated papers with figures, tables, or statistics should be verifiable. An agent that executes code and validates results is cutting-edge.

**What to build:**
- [x] New `code_execution.py` node — extracts code blocks from generated sections
- [x] Optional: Docker sandbox for safe execution
- [x] Verify numerical results match paper claims
- [x] Report discrepancies in `math_verification_report`
- [x] Generate runnable notebooks (.ipynb) alongside paper

**Feasibility:** Low-Medium. Docker sandbox is complex. Start with basic extraction + verification.

---

## Priority 6: Overleaf Push/Pull Integration (P2 — Medium Value, Medium Complexity)

**Why:** Overleaf is the de-facto LaTeX editor. Pushing artifacts directly saves a manual upload step.

**What to build:**
- [x] New `output/overleaf.py` enhancements (exists as stub)
- [x] Push mode: upload `main.tex` + `references.bib` to Overleaf project via API
- [x] Pull mode: sync changes from Overleaf back into the agent's state
- [x] OAuth2 or token-based auth for Overleaf API
- [x] UI button: "Open in Overleaf"

**Feasibility:** Medium. Overleaf API exists but has rate limits. File already exists as stub.

---

## Priority 7: Citation Network Visualization (P2 — Medium Value, Medium Complexity)

**Why:** A visual graph of citations and related papers helps users understand the research landscape at a glance.

**What to build:**
- [x] New `/api/runs/{run_id}/citation-graph` endpoint
- [x] Use existing citation data + OpenAlex citation links
- [x] Return D3.js/React-Flow compatible format (nodes = papers, edges = citations)
- [x] Web UI: interactive force-directed graph
- [x] Click paper node → show abstract, metadata


**Feasibility:** Medium. Visualization is new, but data is already available.

---

## Priority 8: Dataset Discovery (P2 — Medium Value, Medium Complexity)

**Why:** Connecting research questions to relevant datasets from Hugging Face and Kaggle bridges the gap between theory and experimentation.

**What to build:**
- [x] New `tools/huggingface.py` adapter — search datasets by topic
- [x] New `tools/kaggle.py` adapter — search Kaggle datasets
- [x] New node `dataset_discovery.py` — identifies relevant datasets for the research topic
- [x] Include dataset links, descriptions, and download counts in artifacts
- [x] UI: "Datasets" tab showing discovered datasets

**Feasibility:** High. Simple API queries. Reuse existing tool pattern.

---


## Priority 9: Grant Proposal Generator (P3 — Medium Value, Low-Medium Complexity)

**Why:** Researchers need grant proposals. Leveraging existing research output to auto-generate proposal drafts saves significant time.

**What to build:**
- [x] New `grant_proposal.py` node
- [x] Takes topic + generated sections + peer review
- [x] Generates: Title, Abstract, Problem Statement, Methodology, Timeline, Budget Justification, Expected Impact
- [x] Export as PDF/Markdown/LaTeX
- [x] Templates for NSF, NIH, ERC formats

**Feasibility:** Medium. Reuses LLM + LaTeX infrastructure. Domain-specific templates needed.

---

## Priority 10: Research Trends Dashboard (P3 — Low Value, High Complexity)

**Why:** Trending topics and analytics help users decide what to research.

**What to build:**
- [x] Aggregate search across ArXiv / Semantic Scholar for recent papers
- [x] Topic trend analysis (rising/falling keywords)
- [x] Dashboard UI with charts (paper count over time, top authors, top institutions)
- [x] Weekly trend report email

**Feasibility:** Low. Heavy data pipeline. Requires significant infrastructure.


---

## Implementation Roadmap

```
Phase 1 (COMPLETE) — Fast Wins
├── Paper-to-Blog Generator (P0)     ✅ Done
├── Interactive LaTeX Preview (P0)   ✅ Done
└── Dataset Discovery (P2)           ✅ Done

Phase 2 (COMPLETE) — Core Enhancement
├── Research Q&A Chatbot (P1)        ✅ Done
├── Multi-Paper Survey Gen (P1)      ✅ Done
└── Citation Network Vis (P2)        ✅ Done

Phase 3 (COMPLETE) — Advanced
├── Code Execution Verif. (P1)       ✅ Done
├── Overleaf Integration (P2)        ✅ Done
└── Grant Proposal Gen (P3)          ✅ Done

Phase 4 (COMPLETE) — Future
└── Research Trends Dashboard (P3)   ✅ Done
```

---

## Bug Fixes Applied (June 2026)

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `webapp.py:909` | `y.isdigit()` crashes when year is `int` (from Semantic Scholar) | Wrapped with `str(y).isdigit()` |
| 2 | `webapp.py` | Missing `POST /api/session/{sid}/stop` REST endpoint — frontend fallback fails when WebSocket is down | Added REST stop endpoint that delegates to `stop_session_run()` |
| 3 | `dataset_discovery.py:3` | Unused `asyncio` import (ruff F401) | Removed |

---

## Phase 5: Collaborative & Intelligent Research (Next Sprint)

### Priority 11: Multi-User Collaborative Research Sessions
**Why:** Research is collaborative. Multiple researchers should be able to contribute to the same paper in real time — editing sections, adding comments, and resolving conflicts.

**What to build:**
- [ ] Shared session model: invite collaborators by email, assign roles (lead, contributor, reviewer)
- [ ] Real-time co-editing via WebSocket broadcast (operational transform or CRDT for conflict resolution)
- [ ] Per-section locking and merge resolution when two users edit the same section
- [ ] Comment threads on generated sections (similar to Google Docs suggestions)
- [ ] Activity feed: who changed what, when
- [ ] Permission model: viewer / commenter / editor / admin

**Feasibility:** Medium-High. Significant WebSocket infrastructure expansion. Auth model already supports users.

---

### Priority 12: AI Model Router & Multi-Provider Support
**Why:** Different LLM providers excel at different tasks. A smart model router selects the best model per task (planning vs writing vs math verification) and provides fallback resilience.

**What to build:**
- [ ] Model router config: map task types (plan, write, critique, code) to specific models
- [ ] Support OpenAI, Anthropic, Google Gemini, Ollama (local), Groq, and NVIDIA NIM
- [ ] Automatic fallback chain: if primary model fails, try secondary, then tertiary
- [ ] Cost tracking per model per run with budget enforcement
- [ ] Latency-aware routing: prefer faster models for interactive tasks
- [ ] Settings UI: let users configure their preferred models and API keys

**Feasibility:** Medium. Requires abstracting the current NVIDIA-centric model layer into a multi-provider system.

---

### Priority 13: Automated Literature Monitoring & Alerting
**Why:** Researchers need to stay current. An automated watchdog that monitors new publications on their topics and alerts them is high-value.

**What to build:**
- [ ] Scheduled background jobs (APScheduler or Celery) that poll ArXiv/Semantic Scholar daily
- [ ] Diff detection: identify genuinely new papers since last check
- [ ] Relevance scoring: rank new papers against user's research profile/topics
- [ ] Email digest with summaries, links, and relevance scores
- [ ] Dashboard widget showing latest papers in user's field
- [ ] "One-click deep dive": launch a full research run from a discovered paper

**Feasibility:** Medium. Watchdog subscription endpoints already exist. Needs scheduled task infrastructure.

---

### Priority 14: Research Knowledge Graph Explorer
**Why:** The system already builds knowledge graphs per run, but they're siloed. A cross-run, persistent knowledge graph enables researchers to explore connections across all their past research.

**What to build:**
- [ ] Persistent Neo4j or NetworkX graph store aggregating entities across all runs
- [ ] Entity deduplication and merge across runs (same author, concept, or paper)
- [ ] Interactive 3D graph explorer (WebGL-based, three.js or Sigma.js)
- [ ] Semantic search over the knowledge graph ("find all papers connecting X to Y")
- [ ] Export subgraphs as SVG/PNG for inclusion in papers
- [ ] "Research map" visualization: user's entire research landscape at a glance

**Feasibility:** Medium-High. Knowledge graph nodes already exist per-run. Needs persistent store and aggregation layer.

---

### Priority 15: Intelligent Research Assistant (Agentic Chat)
**Why:** Move beyond simple Q&A. The chat should proactively suggest next steps, identify gaps in the user's research, and autonomously execute multi-step research plans.

**What to build:**
- [ ] Agentic chat mode: user gives a high-level goal, agent breaks it into steps and executes
- [ ] Tool-calling chat: agent can invoke search, citation check, dataset discovery, etc. mid-conversation
- [ ] Memory across sessions: recall past conversations, research context, and user preferences
- [ ] Proactive suggestions: "Your paper is missing references from the last 2 years in this subtopic"
- [ ] Research planning assistant: help users design experiments, formulate hypotheses
- [ ] Integration with existing graph pipeline: kick off full runs from chat context

**Feasibility:** High. Leverages existing infrastructure. Primary work is in prompt engineering and orchestration logic.

---

## Phase 6: Production Hardening & Scalability

### Priority 16: Async Job Queue & Worker Scaling
**What to build:**
- [ ] Replace in-process graph execution with Celery/RQ-based distributed task queue
- [ ] Redis-backed job tracking with progress, cancellation, and retry support
- [ ] Horizontal scaling: multiple worker processes for concurrent research runs
- [ ] Job priority queue: interactive requests get priority over background jobs
- [ ] Dead letter queue and failure alerting

---

### Priority 17: Comprehensive Observability & Monitoring
**What to build:**
- [ ] OpenTelemetry integration for distributed tracing across all nodes
- [ ] Prometheus metrics: request latency, LLM token usage, error rates, queue depth
- [ ] Grafana dashboard templates for operational monitoring
- [ ] Structured JSON logging with correlation IDs across the full pipeline
- [ ] Cost analytics dashboard: track and visualize API spending per user/run

---

### Priority 18: Security Hardening & Enterprise Features
**What to build:**
- [ ] Rate limiting per user and per endpoint (slowapi or custom middleware)
- [ ] Input sanitization and prompt injection defense
- [ ] Audit logging: who accessed what data, when
- [ ] SSO/SAML integration for enterprise deployments
- [ ] Data retention policies and GDPR compliance tooling
- [ ] Role-based access control (RBAC) beyond simple auth

---

### Priority 19: Plugin & Extension System
**What to build:**
- [ ] Plugin API: allow third-party nodes to be registered at runtime
- [ ] Hook system: before/after each graph node for custom processing
- [ ] Custom tool adapters: user-defined search sources (Google Scholar, PubMed, DBLP)
- [ ] Template marketplace: community-contributed LaTeX templates
- [ ] Export plugins: custom output formats (Word, EPUB, conference submission systems)

---

### Priority 20: Mobile & Offline Support
**What to build:**
- [ ] Progressive Web App (PWA) with offline caching of generated papers
- [ ] Responsive mobile-first UI redesign
- [ ] Background sync: queue research requests offline, execute when connected
- [ ] Push notifications for long-running research completion
- [ ] Local-first mode: run with Ollama for fully offline research

---

## Next Steps

**Recommended starting order for Phase 5:**

1. **Priority 15: Intelligent Research Assistant** — highest value-to-effort ratio. Builds on existing chat infrastructure and requires mostly prompt engineering.
2. **Priority 12: AI Model Router** — immediate operational benefit. Reduces cost and improves resilience.
3. **Priority 13: Literature Monitoring** — watchdog endpoints already exist. Needs scheduling layer.

**For Phase 6**, prioritize **Priority 16 (Job Queue)** first — it unblocks horizontal scaling and makes all other production features viable.
