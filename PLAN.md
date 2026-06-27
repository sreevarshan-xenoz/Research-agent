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
- [ ] New `tools/huggingface.py` adapter — search datasets by topic
- [ ] New `tools/kaggle.py` adapter — search Kaggle datasets
- [ ] New node `dataset_discovery.py` — identifies relevant datasets for the research topic
- [ ] Include dataset links, descriptions, and download counts in artifacts
- [ ] UI: "Datasets" tab showing discovered datasets

**Feasibility:** High. Simple API queries. Reuse existing tool pattern.

---

## Priority 9: Grant Proposal Generator (P3 — Medium Value, Low-Medium Complexity)

**Why:** Researchers need grant proposals. Leveraging existing research output to auto-generate proposal drafts saves significant time.

**What to build:**
- [ ] New `grant_proposal.py` node
- [ ] Takes topic + generated sections + peer review
- [ ] Generates: Title, Abstract, Problem Statement, Methodology, Timeline, Budget Justification, Expected Impact
- [ ] Export as PDF/Markdown/LaTeX
- [ ] Templates for NSF, NIH, ERC formats

**Feasibility:** Medium. Reuses LLM + LaTeX infrastructure. Domain-specific templates needed.

---

## Priority 10: Research Trends Dashboard (P3 — Low Value, High Complexity)

**Why:** Trending topics and analytics help users decide what to research.

**What to build:**
- [ ] Aggregate search across ArXiv / Semantic Scholar for recent papers
- [ ] Topic trend analysis (rising/falling keywords)
- [ ] Dashboard UI with charts (paper count over time, top authors, top institutions)
- [ ] Weekly trend report email

**Feasibility:** Low. Heavy data pipeline. Requires significant infrastructure.

---

## Implementation Roadmap

```
Phase 1 (Current Sprint) — Fast Wins
├── Paper-to-Blog Generator (P0)     ~1-2 days
├── Interactive LaTeX Preview (P0)   ~2-3 days  
└── Dataset Discovery (P2)           ~1 day

Phase 2 — Core Enhancement
├── Research Q&A Chatbot (P1)        ~3-4 days
├── Multi-Paper Survey Gen (P1)      ~3-5 days
└── Citation Network Vis (P2)        ~2-3 days

Phase 3 — Advanced
├── Code Execution Verif. (P1)       ~5-7 days
├── Overleaf Integration (P2)         ~2-3 days
└── Grant Proposal Gen (P3)          ~2-3 days

Phase 4 — Future
└── Research Trends Dashboard (P3)   ~5-7 days
```

---

## Recommendation

**Start with Phase 1** — these are fast, high-value, and visibly impressive:

1. **Paper-to-Blog Generator** — highest value per unit effort. Single new node.
2. **Interactive LaTeX Preview** — biggest "wow factor" for the UI. 
3. **Dataset Discovery** — easy addition that connects to the broader AI ecosystem.

These build on existing infrastructure and deliver immediate, demo-able results.
