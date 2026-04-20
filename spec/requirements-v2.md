# Research Agent v2 Requirements Specification

## 1. Document Control
- Version: 2.0
- Date: 2026-04-20
- Status: Draft for implementation
- Scope: Version 2 (Multi-provider, Parallel, Local/Cloud Hybrid)

## 2. Product Summary
Research Agent v2 is a major upgrade introducing multi-provider LLM support (Ollama, OpenRouter, Puter), parallel subagent execution for faster generation, 2-column IEEE format support, and enhanced retrieval from multiple academic sources.

## 3. Goals and Non-Goals
### 3.1 Goals
- **Multi-Provider LLM:** Support local (Ollama) and cloud (OpenRouter, Puter) models with priority-based routing and fallback.
- **Parallel Execution:** Execute multiple subagent tasks concurrently to reduce total generation time.
- **Advanced Formatting:** Support IEEE Two-Column format and template selection API.
- **Enhanced Retrieval:** Integrate ArXiv, Semantic Scholar, and OpenAlex for comprehensive source discovery.
- **Improved UX:** Two-column workbench with live LaTeX preview and better error handling.
- **Direct PDF Export:** Support generating PDF artifacts directly using Tectonic/pdflatex.

### 3.2 Non-Goals (v2)
- Real-time multi-user collaboration (planned for v2.2+).
- Advanced figure/table auto-generation (planned for v2.2+).
- Multi-tenant enterprise deployment.

## 4. Users and Stakeholders
- Primary user: Researchers needing high-quality, formatted drafts quickly.
- Secondary user: Developers wanting to run research agents locally for privacy or cost reasons.

## 5. Core User Stories (New for v2)
- As a user, I can run the system entirely locally using Ollama to save costs and ensure privacy.
- As a user, I can generate a 2-column IEEE paper directly from the UI.
- As a user, I can see the system synthesize multiple sections in parallel.
- As a user, I can export a finished PDF of my research paper.

## 6. Functional Requirements

### 6.1 Multi-Provider LLM (NEW)
- FR-038: System shall support local LLM inference via Ollama.
- FR-039: System shall support cloud LLM inference via OpenRouter (free tier).
- FR-040: System shall implement priority-based routing: Ollama -> OpenRouter -> Puter -> Fallback.
- FR-041: System shall use LiteLLM for unified model interaction and automated fallback.

### 6.2 Parallel Subagent Execution (NEW)
- FR-042: System shall implement a Worker Pool for parallel execution of subtopic tasks.
- FR-043: System shall allow configuring `OLLAMA_NUM_PARALLEL` for concurrent local requests.
- FR-044: System shall distribute tasks based on complexity and provider availability.

### 6.3 Document Format and Templating (UPDATED)
- FR-045: System shall support IEEE Two-Column format.
- FR-046: System shall provide a Template Selection API (ieee-1col, ieee-2col, acm, springer).
- FR-047: System shall support mixed single/double column floats in LaTeX.

### 6.4 Retrieval and Sources (UPDATED)
- FR-048: System shall integrate OpenAlex as a primary paper provider.
- FR-049: System shall implement fuzzy deduplication for retrieved papers (SHA1 fingerprint).
- FR-050: System shall support advanced web search depth (hybrid duckduckgo + browser_use).

### 6.5 New Features (NEW)
- FR-051: System shall implement Citation Auto-Fix using Semantic Scholar/CrossRef APIs.
- FR-052: System shall support multi-language templates (en, zh, ja, etc.).
- FR-053: System shall support direct PDF export using Tectonic.

### 6.6 Web UX (UPDATED)
- FR-054: UI shall provide a two-column workbench with Doc and LaTeX tabs.
- FR-055: UI shall include a Provider Selector for manual or auto-selection.
- FR-056: UI shall display session-persistent updates via WebSocket or local storage.

## 7. Non-Functional Requirements

### 7.1 Performance (UPDATED)
- NFR-001 (v2): Section generation time target: < 15 seconds (3x faster than v1).
- NFR-002 (v2): Support at least 4 concurrent workers by default.

### 7.2 Reliability (UPDATED)
- NFR-003 (v2): Automated provider fallback must succeed within 5 seconds of failure detection.

## 8. Data and Artifact Requirements
- DR-005: Persist session state in Redis or localStorage for recovery.

## 9. Constraints and Assumptions
- C-004: Local model performance depends on user hardware (RTX 3090+ recommended for best results).
- C-005: OpenRouter free tier is subject to rate limits (20 req/min).

## 10. Acceptance Criteria (v2)
- AC-006: Successful 2-column IEEE paper generation with valid PDF export.
- AC-007: Verified parallel execution of at least 4 worker tasks simultaneously.
- AC-008: Verified fallback from local Ollama to cloud OpenRouter on local failure.

## 11. Requirement Traceability (v2)
- Multi-provider: FR-038 to FR-041
- Parallelism: FR-042 to FR-044
- Formatting: FR-045 to FR-047, FR-053
- Retrieval: FR-048 to FR-050
- Features & UX: FR-051 to FR-052, FR-054 to FR-056
