# Research Agent v2 Implementation Plan

## 1. Plan Objective
Upgrade the Research Agent from a single-provider API-based system to a multi-provider, parallel, hybrid local/cloud system with advanced document formatting.

## 2. Core v2 Goals
- Parallel subagent execution (speed).
- Hybrid local/cloud model support (cost/privacy).
- Advanced document formatting (IEEE 2-column, direct PDF).

## 3. Phase and Milestone Plan

### Milestone M0: Foundation (v2.0)
*Status: Current Phase*
- [x] Multi-provider architecture with LiteLLM.
- [x] Parallel subagent execution (Worker Pool).
- [x] IEEE 2-column LaTeX template.
- [x] Provider priority routing and fallback.

### Milestone M1: Reliability and UX (v2.1)
*Timeline: Next 2-3 Weeks*
- [ ] **Citation Auto-Fix:** Automated background verification of references.
- [ ] **Session Persistence:** State recovery using localStorage or session-based Redis.
- [ ] **Error Visuals:** Advanced error banners and status indicators in UI.
- [ ] **OpenAlex Integration:** Full academic network enrichment.

### Milestone M2: Advanced Features (v2.2)
*Timeline: 1-2 Months*
- [ ] **Direct PDF Export:** Implementation of Tectonic for one-click PDF generation.
- [ ] **Multi-Language Templates:** Support for non-English outputs (Jinja2 updates).
- [ ] **Real-time Live Preview:** Live side-by-side LaTeX and Doc view.
- [ ] **Figure Generation:** Mermaid/PlantUML integration for automated diagrams.

### Milestone M3: Scale and Optimization (v2.3)
*Timeline: 3+ Months*
- [ ] **Redis-Backed State:** Production-grade state management.
- [ ] **vLLM Integration:** High-throughput local inference option.
- [ ] **Multi-User Collaboration:** WebSocket-based session sharing.
- [ ] **Cloud Deployment:** Dockerization and deployment templates for AWS/Azure.

## 4. Key Implementation Tasks

### 4.1 Parallel Execution
- Refactor `WorkerNode` to support concurrent execution via `asyncio.Semaphore`.
- Implement complexity scoring for task distribution.
- Add hardware-aware auto-tuning for `OLLAMA_NUM_PARALLEL`.

### 4.2 Multi-Provider LLM
- Integrate LiteLLM for `ollama`, `openrouter`, and `puter`.
- Build the model routing logic with priority and fallback support.
- Centralize model config in `configs/settings.v2.yaml`.

### 4.3 Output Engine
- Create `ieee-2col` Jinja2 templates.
- Update `LaTeXRenderer` to handle multi-column environments.
- Implement PDF generation wrapper for Tectonic.

### 4.4 Web Application
- Re-design the UI for a two-column workbench.
- Implement live status updates via WebSockets or polling.
- Add provider and template selection controls.

## 5. Risk and Mitigation Strategy
- **Risk:** Hardware limitations for local models.
  - *Mitigation:* Graceful fallback to OpenRouter free models if Ollama fails or is unavailable.
- **Risk:** Complex LaTeX builds fail.
  - *Mitigation:* Robust error reporting and raw LaTeX export as a fallback to PDF.
- **Risk:** API rate limits.
  - *Mitigation:* Parallelization with rate-limit awareness and exponential backoff.

## 6. Definition of Done (v2.0)
- End-to-end 2-column IEEE paper generated successfully.
- Successful parallel execution of 4+ subagents.
- Verified fallback from local to cloud providers.
- PDF export generated (manually or via Tectonic).
