# Research Agent v2 Design Specification

## 1. Design Scope
This document defines the v2 technical design for a multi-provider LLM, parallel subagent research system with local/cloud hybrid execution and advanced LaTeX/PDF output.

## 2. Architecture Overview

### 2.1 Component Evolution (New in v2)
- **Multi-Provider Hub (LiteLLM):** Manages local (Ollama) and cloud (OpenRouter) LLM routing.
- **Parallel Worker Pool:** Manages concurrent subagent execution with hardware-aware concurrency limits.
- **Enhanced Retrieval Engine:** Multi-source discovery (ArXiv, Semantic Scholar, OpenAlex) with fuzzy deduplication.
- **Advanced LaTeX Renderer:** Support for multi-column templates (IEEE 2-column) and Tectonic PDF generation.
- **Workbench UI:** Enhanced Gradio/Web interface with live LaTeX preview and session persistence.

### 2.2 Tech Stack (v2 Updates)
- LLM Router: LiteLLM
- Concurrency: asyncio Semaphore / WorkerPool
- PDF Engine: Tectonic
- State Persistence: Redis / localStorage (Session based)
- Deduplication: SHA1 fingerprints for research papers

## 3. Multi-Provider LLM Design

### 3.1 Routing Strategy
- **Priority Order:** Local Ollama (Primary) -> OpenRouter Free (Secondary) -> Puter (Fallback).
- **Complexity Scoring:** Task complexity (1-10) determines provider selection (High complexity -> Reasoning models like DeepSeek-R1).
- **Environment Overrides:** `MODEL_PROVIDER_PRIORITY`, `ORCHESTRATOR_MODEL`, `SUBAGENT_MODEL`.

### 3.2 LiteLLM Implementation
- Unified `completion()` calls with automated `fallbacks` list.
- Config-driven model list for easy addition of new providers.

## 4. Parallel Subagent Execution Design

### 4.1 Worker Pool Architecture
- `WorkerPool` class managing an `asyncio.Semaphore`.
- Hardware-based default concurrency (e.g., 4 workers for RTX 3090/4090).
- Task distribution based on section types and complexity scores.

### 4.2 Synchronization
- Async synchronization barriers before the Combination and Critique phases.
- Partial result preservation on worker failure.

## 5. Output and Templating Design

### 5.1 Multi-Column Support
- `ieee-2col` template utilizing `\documentclass[conference,twocolumn]{IEEEtran}`.
- Conditional template logic in Jinja2 to support 1-column vs 2-column layouts.
- Support for `figure*` and `table*` environments for full-width elements in multi-column layouts.

### 5.2 PDF Generation
- Integration with `tectonic` for fast, cross-platform PDF export.
- Automated font and package handling during the build process.

## 6. Retrieval Engine v2

### 6.1 Source Integration
- Dedicated adapters for ArXiv, Semantic Scholar, and OpenAlex.
- Author network and cross-reference expansion in OpenAlex.

### 6.2 Deduplication
- SHA1 hashing of paper titles and abstracts to prevent redundant processing.
- Metadata merging when the same paper is found across multiple providers.

## 7. Web UX v2 Design

### 7.1 Workbench Layout
- **Two-Column View:** Interactive editor on the left, live LaTeX/PDF preview on the right.
- **Tabs:** Doc (Quill), LaTeX (Raw), Evidence (Sources), Stats (Confidence/Cost).
- **Controls:** Provider selector, template toggle, search depth settings.

### 7.2 Error Handling
- Visual error banners for provider failures.
- Session expiry notifications and automatic reconnects.

## 8. New Feature Components

### 8.1 Citation Auto-Fixer
- Background worker to validate and repair broken citations using DOI/Title lookups.
- Integration with Semantic Scholar and CrossRef APIs.

### 8.2 Figure Generator
- Mermaid/PlantUML integration for automated diagram generation from section text.

## 9. Design Risks and Mitigations (v2)
- **Risk:** Local model context limits vs Cloud models.
  - *Mitigation:* Use Cloud models for long-context synthesis if local models fail.
- **Risk:** Concurrency bottlenecks in Ollama.
  - *Mitigation:* Fine-tune `OLLAMA_NUM_PARALLEL` and implement request queuing.
- **Risk:** Template breakage in 2-column layout.
  - *Mitigation:* Extensive Jinja2 testing for multi-column edge cases.

## 10. Forward Compatibility (v3)
- Real-time WebSockets for multi-user support.
- Redis-backed state for cluster deployment.
