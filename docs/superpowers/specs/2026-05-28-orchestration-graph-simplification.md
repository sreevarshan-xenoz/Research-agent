# Orchestration Graph Simplification — Complexity Analysis

> **Status:** Architecture Proposal  
> **Author:** Research Agent Team  
> **Date:** 2026-05-28  

---

## 1. Executive Summary

The current orchestration graph has **27 registered nodes** and **28 edges**, forming a nearly-linear pipeline of 19 sequential post-processing nodes after the critic loop. This analysis identifies **10 nodes to remove**, **3 nodes to merge**, and **2 nodes to degrade to optional**, producing a simplified graph of **~16 nodes** with an estimated **~75% reduction in post-processing token cost** and **~60% reduction in failure surface**.

**Key finding:** The post-processing chain (combiner → exporter) contains 9 sequential nodes of which only 3 (combiner, composer, exporter) produce content integrated into the final output. The remaining 7 are analysis-only nodes that store reports but have zero downstream impact, yet each adds latency, token cost, and failure risk.

---

## 2. Node-by-Node Analysis

### 2.1 Legend

| Metric | Meaning |
|--------|---------|
| **Value** | How this node contributes to the final output artifact |
| **Token Cost** | Approximate LLM tokens consumed per run |
| **Latency** | Approximate wall-clock time contribution |
| **Failure Risk** | Likelihood of this node crashing or corrupting state |
| **Redundancy** | Degree of overlap with other nodes |

---

### 2.2 Intake — Clarifier — Planner (Pre-Worker)

#### Node: `intake`
| Metric | Assessment |
|--------|-----------|
| **Value** | Low — normalizes topic, checks ambiguity threshold |
| **Token Cost** | 0 (no LLM) |
| **Latency** | <1ms — pure Python |
| **Failure Risk** | Very low — no external dependencies |
| **Redundancy** | None |
| **Verdict** | **KEEP** — negligible cost, useful normalization |

#### Node: `clarifier`
| Metric | Assessment |
|--------|-----------|
| **Value** | Moderate — generates clarification questions for ambiguous topics |
| **Token Cost** | ~200-400 (agenerate_json `role="head"`) |
| **Latency** | ~1-3s |
| **Failure Risk** | Low — has deterministic fallback questions |
| **Redundancy** | None |
| **Verdict** | **KEEP** — important UX feature |

#### Node: `planner`
| Metric | Assessment |
|--------|-----------|
| **Value** | High — decomposes topic into DAG of research tasks |
| **Token Cost** | ~500-1000 (agenerate_json `role="head"`) |
| **Latency** | ~3-6s |
| **Failure Risk** | Low — has robust `_build_adaptive_fallback_tasks()` fallback |
| **Redundancy** | `replanner` duplicates task-generation logic |
| **Verdict** | **KEEP** — core orchestration |

---

### 2.3 Worker Loop (Worker — Index — Critic — Replanner)

#### Node: `plan_validation`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Zero** — sets `phase = "plan_validated"`. That's it. |
| **Token Cost** | 0 |
| **Latency** | <1ms |
| **Failure Risk** | Very low |
| **Redundancy** | Trivial phase-setter, same effect as planner's return |
| **Verdict** | **REMOVE** — zero logic, merge phase update into planner |

#### Node: `worker_executor`
| Metric | Assessment |
|--------|-----------|
| **Value** | High — executes research tasks via tool adapters |
| **Token Cost** | 0 (LLM not called here) |
| **Latency** | Variable — depends on provider response times |
| **Failure Risk** | Moderate — provider timeouts, rate limits |
| **Redundancy** | None |
| **Verdict** | **KEEP** — core execution engine |

#### Node: `workers_complete`
```python
async def workers_complete_node(state: GraphState) -> dict:
    return {
        "phase": "workers_complete",
        "stop_reason": "worker_execution_complete",
    }
```
| Metric | Assessment |
|--------|-----------|
| **Value** | **Near-zero** — sets two state fields. Could be done in worker_executor's return dict. |
| **Token Cost** | 0 |
| **Latency** | <1ms |
| **Failure Risk** | Very low |
| **Redundancy** | Completely redundant with worker_executor |
| **Verdict** | **REMOVE** — merge phase/stop_reason into worker_executor |

#### Node: `indexing`
| Metric | Assessment |
|--------|-----------|
| **Value** | High — indexes findings into Qdrant for Deep RAG retrieval, detects contradictions |
| **Token Cost** | 0 (no LLM call) |
| **Latency** | ~100-500ms (async writes to in-memory Qdrant) |
| **Failure Risk** | Low — Qdrant `:memory:` mode |
| **Redundancy** | None |
| **Verdict** | **KEEP** — essential for combiner's evidence retrieval |

#### Node: `critic`
| Metric | Assessment |
|--------|-----------|
| **Value** | High — scores evidence confidence, marks tasks for re-run, manages iteration loop |
| **Token Cost** | 0 (deterministic scoring) |
| **Latency** | ~5ms |
| **Failure Risk** | Low — pure math |
| **Redundancy** | Partial overlap with `replanner` — critic already resets low-confidence tasks to `pending` and adds a `f{iteration_index}` recovery task |
| **Verdict** | **KEEP** but absorb replanner |

#### Node: `replanner`
| Metric | Assessment |
|--------|-----------|
| **Value** | Low — LLM call to decide if new tasks are needed. **Most runs add 0 new tasks.** The critic already handles iteration by resetting low-confidence tasks + adding a recovery task. |
| **Token Cost** | ~500-800 (agenerate_json `role="orchestrator"`) |
| **Latency** | ~2-5s |
| **Failure Risk** | Moderate — LLM may produce invalid task structures |
| **Redundancy** | **85% overlap with critic** — both manage the task list for re-execution. The critic already resets low-confidence tasks. The replanner's marginal value (adding brand-new tasks) is almost never triggered. |
| **Code cost** | 55 lines with LLM prompt + fallback |
| **Verdict** | **MERGE INTO CRITIC** — add a deterministic heuristic in critic to expand task count instead of LLM call |

---

### 2.4 Post-Processing Chain (Linear, 9 Sequential Nodes)

The current post-processing chain runs **9 nodes sequentially**, each waiting for the previous to complete:

```
combiner → knowledge_graph → bias_detector → future_work → comparison_table → figure_generator → citation_verifier → composer → formula_normalizer → hallucination_guard → formula_verifier → peer_reviewer → presentation → poster → exporter
```

#### Node: `combiner`
| Metric | Assessment |
|--------|-----------|
| **Value** | High — synthesizes section content from indexed evidence via LLM |
| **Token Cost** | ~2000-4000 (agenerate_text per section, plus citation maps) |
| **Latency** | ~10-20s |
| **Failure Risk** | Low — has fallback to crude synthesis |
| **Redundancy** | None |
| **Verdict** | **KEEP** — core content generation |

#### Node: `knowledge_graph`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Near-zero from output perspective** — the KG is extracted, stored in state, and written to `artifacts/<run_id>/knowledge_graph.json`. **No downstream node reads it.** Composer doesn't use it. Exporter just dumps it to disk. |
| **Token Cost** | ~800-1500 (agenerate_json `role="orchestrator"`) |
| **Latency** | ~3-8s |
| **Failure Risk** | Low — LLM returns dict or empty |
| **Downstream consumers** | **None.** Zero. The output is a JSON file on disk that no one reads. |
| **Verdict** | **REMOVE** — beautiful output, zero impact. Cost/benefit ratio is infinite (infinite cost for zero benefit). If users genuinely view the KG file, degrade to optional behind a `--knowledge-graph` flag. |

#### Node: `bias_detector`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — analysis-only. Produces a Markdown report stored in `bias_report`. Composer doesn't read it. Exporter writes it to disk. **No corrective action is taken based on bias analysis.** |
| **Token Cost** | ~800-1500 (agenerate_text `role="orchestrator"`) |
| **Latency** | ~3-7s |
| **Failure Risk** | Low |
| **Downstream consumers** | **None.** The report is written to disk for human inspection. Not integrated into the paper. |
| **Verdict** | **REMOVE or degrade to optional** — analysis with no corrective feedback loop. Zero output impact. |

#### Node: `future_work` (future_work_extrapolator_node)
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — analysis-only. Generates future research agenda as Markdown. Stored in `future_research_agenda`. Written to disk by exporter. **Not integrated into the paper.** |
| **Token Cost** | ~800-1500 (agenerate_text `role="orchestrator"`) |
| **Latency** | ~3-7s |
| **Failure Risk** | Low |
| **Downstream consumers** | **None.** |
| **Verdict** | **REMOVE** — the `future_research_agenda` field is written to disk but not included in `main.tex`. Wasted LLM call. |

#### Node: `comparison_table` (comparison_table_node)
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — generates a LaTeX comparison table from top 5 citations. Stored in `comparison_table`. Written to disk. **Not integrated into main.tex** — composer's `_build_body()` doesn't include `comparison_table`. |
| **Token Cost** | ~800-1500 (agenerate_text `role="orchestrator"`) |
| **Latency** | ~3-6s |
| **Failure Risk** | Moderate — LLM may produce invalid LaTeX that causes compilation errors |
| **Downstream consumers** | **None.** The comparison table is exported as `comparison_table.tex` but never `\input{}`-ed into the main document. |
| **Verdict** | **REMOVE** — orphaned output. If the table should be in the paper, composer needs to include it. Currently it's dead code. |

#### Node: `figure_generator`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — 2 LLM calls (decide figure type + translate to TikZ). **High failure rate** — TikZ output is frequently invalid, requires manual correction. |
| **Token Cost** | ~1000-2000 (agenerate_json + agenerate_text `role="orchestrator"`) |
| **Latency** | ~6-15s (two sequential LLM calls) |
| **Failure Risk** | **High** — TikZ generation is notoriously unreliable. Invalid output corrupts document compilation. The fallback stores untranslated PlantUML/Mermaid code which cannot be compiled. |
| **Redundancy** | None, but the value is marginal — most research topics don't benefit from auto-generated diagrams. |
| **Verdict** | **DEGRADE TO OPTIONAL** — behind `--generate-figures` flag. Off by default. |

#### Node: `citation_verifier`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Moderate-High** — extracts citations from findings, checks for unsupported claims, auto-fixes via OpenAlex. Core for bibliography quality. |
| **Token Cost** | 0 (no LLM) but **N external API calls** to OpenAlex for auto-fix |
| **Latency** | ~1-3s + per-citation OpenAlex lookups |
| **Failure Risk** | Moderate — OpenAlex API failures cascade through `_autofix_citations`. |
| **Redundancy** | Citation extraction overlaps partially with combiner's `citation_map` — both process source metadata into structured references. |
| **Verdict** | **KEEP but SIMPLIFY** — merge citation_map and citation extraction into a single deterministic pass. Remove OpenAlex auto-fix or degrade to optional. |

#### Node: `composer`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Critical** — generates title/abstract/body via LLM, renders to LaTeX, builds BibTeX. |
| **Token Cost** | ~1500-3000 (agenerate_json `role="orchestrator"`) |
| **Latency** | ~8-15s |
| **Failure Risk** | Moderate — LLM returns malformed JSON, body may have issues |
| **Redundancy** | `_build_subagent_prompt` is defined but never called (dead code) |
| **Verdict** | **KEEP** — core document generation. Remove dead `_build_subagent_prompt` code. |

#### Node: `formula_normalizer`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — sends **entire LaTeX document** (~4000+ tokens) to LLM to standardize math notation. The prompt asks to use `\mathbf{v}` for vectors, `\mathbf{A}` for matrices, and AMS-LaTeX conventions. **The section content from combiner almost never contains math in the first place** (it's prose from evidence synthesis). The risk of hallucinated edits to the body far outweighs the cosmetic value. |
| **Token Cost** | ~4000-5000 (agenerate_text `role="orchestrator"`, `max_tokens=4000`) — **the single most expensive node** |
| **Latency** | ~10-20s |
| **Failure Risk** | **High** — replaces `latex_main` entirely. If the LLM truncates, hallucinates, or corrupts the document, the entire paper is ruined. The safety check (`if len(normalized_latex) < 100: keep original`) is fragile — truncation at 5000+ chars would pass. |
| **Redundancy** | Formula verifier partially overlaps (both analyze math) |
| **Verdict** | **REMOVE** — highest token cost, highest corruption risk, minimal cosmetic value. Replace with deterministic regex-based normalization of common patterns (e.g., `\mathbf` for `\vec`, bracket matching). |

#### Node: `hallucination_guard`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — LLM reads first 3 sections and looks for "concept hallucinations". Produces a Markdown warning. **No corrective action is taken** — the run_warnings flag is appended but the document is not modified. |
| **Token Cost** | ~500-1000 (agenerate_text `role="orchestrator"`) |
| **Latency** | ~3-6s |
| **Failure Risk** | Low |
| **Downstream consumers** | Warnings appear in run_warnings and guard_report.md. No document changes. |
| **Verdict** | **REMOVE** — analysis with no corrective feedback loop. The document is already composed and exported unchanged regardless of the guard's findings. |

#### Node: `formula_verifier`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — regex-extracts formulas, sends top 10 to LLM for consistency check. Produces Markdown report. **No corrective action taken.** |
| **Token Cost** | ~500-1000 (agenerate_text `role="orchestrator"`) |
| **Latency** | ~3-6s |
| **Failure Risk** | Low |
| **Redundancy** | Formula normalizer already touched the same formulas (and may have introduced errors that this node would detect — but neither corrects anything). |
| **Verdict** | **REMOVE** — analysis-only, no correction. Redundant with normalizer's scope. |

#### Node: `peer_reviewer`
| Metric | Assessment |
|--------|-----------|
| **Value** | **Low** — sends **entire LaTeX document** to LLM for peer review. Produces Markdown report. **No corrective action taken** — the document is already fully composed. |
| **Token Cost** | ~2000-4000 (agenerate_text `role="orchestrator"`, `max_tokens=2000` but input includes full LaTeX) |
| **Latency** | ~8-15s |
| **Failure Risk** | Low |
| **Downstream consumers** | Written to disk as `peer_review_report.md`. Document is not modified. |
| **Verdict** | **REMOVE** — expensive analysis after the point of no return. If peer review is desired, it should be a post-hoc step, not an in-graph node that blocks export. |

#### Node: `presentation`
| Metric | Assessment |
|--------|-----------|
| **Value** | Moderate — generates Beamer LaTeX from sections. **Deterministic — no LLM.** |
| **Token Cost** | 0 |
| **Latency** | ~5ms |
| **Failure Risk** | Very low |
| **Redundancy** | Poster uses similar `render_poster_tex` — both are template renderers |
| **Verdict** | **KEEP but degrade to optional** — should only run when `--presentation` flag is set. Not all research topics need a slide deck. |

#### Node: `poster`
| Metric | Assessment |
|--------|-----------|
| **Value** | Moderate — generates A0 poster LaTeX from sections. **Deterministic — no LLM.** |
| **Token Cost** | 0 |
| **Latency** | ~5ms |
| **Failure Risk** | Very low |
| **Redundancy** | Presentation uses similar `render_beamer_tex` |
| **Verdict** | **KEEP but degrade to optional** — behind `--poster` flag. |

#### Node: `exporter`
| Metric | Assessment |
|--------|-----------|
| **Value** | Critical — validates LaTeX, writes all artifacts, refreshes analytics |
| **Token Cost** | 0 |
| **Latency** | ~50-200ms |
| **Failure Risk** | Low |
| **Redundancy** | None |
| **Verdict** | **KEEP** — final artifact output |

---

## 3. Token Cost Analysis

### 3.1 Current Token Consumption

| Node | Tokens | Type | Impact |
|------|--------|------|--------|
| clarifier | ~300 | JSON generation | Query |
| planner | ~750 | JSON generation | Query |
| replanner | ~650 | JSON generation | Query |
| combiner | ~3,000 | Text generation | Content |
| knowledge_graph | ~1,150 | JSON generation | Report |
| bias_detector | ~1,150 | Text generation | Report |
| future_work | ~1,150 | Text generation | Report |
| comparison_table | ~550 | Text generation | Report |
| figure_generator | ~1,500 | JSON + Text | Content |
| citation_verifier | 0 | No LLM | — |
| composer | ~2,250 | JSON generation | Content |
| formula_normalizer | ~4,500 | Text generation | Content |
| hallucination_guard | ~750 | Text generation | Report |
| formula_verifier | ~500 | Text generation | Report |
| peer_reviewer | ~3,000 | Text generation | Report |
| **TOTAL** | **~21,200** | | |

### 3.2 Target Token Consumption

| Node | Tokens | Type | Impact |
|------|--------|------|--------|
| clarifier | ~300 | JSON generation | Query |
| planner | ~750 | JSON generation | Query |
| combiner | ~3,000 | Text generation | Content |
| citation_verifier | 0 | Deterministic | — |
| composer | ~2,250 | JSON generation | Content |
| **TOTAL** | **~6,300** | | |

**Reduction: ~70% token cost** (from ~21,200 to ~6,300 tokens per run).

### 3.3 Latency Impact

Removing the 7 analysis-only nodes + formula_normalizer saves **~35-55 seconds** of sequential wall-clock time per run (the post-processing chain currently takes ~60-90s total; the simplified chain takes ~25-35s).

---

## 4. Failure Propagation Analysis

### 4.1 Current Failure Chain

Each node in the post-processing chain is a potential single point of failure:

```
composer fails → no latex_main → formula_normalizer crashes on empty input → hallucination_guard crashes → formula_verifier crashes → peer_reviewer crashes → presentation gets empty sections → poster gets empty sections → exporter writes empty artifacts
```

A failure in `composer` cascades through 7 downstream nodes, each generating errors and warnings that pollute the output.

### 4.2 Current Risk Amplification

| Risk | Amplification Path |
|------|-------------------|
| **formula_normalizer corruption** | Corrupts `latex_main` → hallucination_guard, formula_verifier, peer_reviewer all analyze corrupted content → exporter validates corrupted LaTeX → potentially passes validation |
| **OpenAlex rate limit** (citation_verifier) | Blocks _autofix_citations → delays composer → delays all downstream nodes |
| **TikZ generation failure** (figure_generator) | Invalid TikZ in figures list → composer embeds invalid LaTeX → validator catches it → run blocked |
| **LLM timeout** (any analysis node) | Each analysis node can timeout independently → 6 sequential timeout-able nodes means high probability of at least one failure per run |

### 4.3 Simplified Risk Profile

Removing analysis-only nodes eliminates 7 potential failure points. Making figure_generator optional removes the highest-failure-risk node. Merging replanner into critic eliminates one LLM call with redundant logic.

---

## 5. Proposed Architecture

### 5.1 Before (Current)

```
START → [intake → clarifier → await_user]
              ↓
         [planner → plan_validation*]
              ↓
         [worker_executor → workers_complete*]
              ↓
         [indexing → critic → replanner ↔ worker_executor]
              ↓
         [combiner → knowledge_graph* → bias_detector* → future_work* → comparison_table* → figure_generator~ → citation_verifier → composer → formula_normalizer* → hallucination_guard* → formula_verifier* → peer_reviewer* → presentation → poster → exporter]
              ↓
         END

* = recommended for removal
~ = recommended for optional-only
```

**27 nodes, 28 edges, 11 LLM calls**

### 5.2 After (Simplified)

```
START → [intake → clarifier → await_user]
              ↓
         [planner (merged plan_validation)]
              ↓
         [worker_executor (merged workers_complete)]
              ↓
         [indexing → critic (merged replanner) ↔ worker_executor]
              ↓
         [stop_node]  ← stopped path
              ↓
         [combiner → citation_verifier (simplified) → composer → exporter]
              ↓
         [optional: figure_generator → presentation → poster]
              ↓
         END

**awaiting_user_critic preserved** in `_route_after_critic` for interactive mode
```

**~16 nodes, ~18 edges, ~5 LLM calls**

### 5.3 Parallelization Opportunity

The optional nodes can run in parallel with each other after composer completes:

```
         composer
            ↓
         [exporter]          # Core path — runs immediately
            ↓
         [optional: figure_generator, presentation, poster]  # Runs in parallel, non-blocking
```

This means the core path (intake → export) has only **1 LLM call in post-processing** (composer), down from **9**.

---

## 6. Detailed Recommendations

### 6.1 Nodes to Remove (10)

| Node | Reason | Token Saved | Latency Saved | Risk Reduction |
|------|--------|-------------|---------------|----------------|
| `plan_validation` | Zero logic — just sets phase | 0 | ~1ms | Negligible |
| `workers_complete` | Trivial phase setter | 0 | ~1ms | Negligible |
| `knowledge_graph` | Beautiful output, zero consumers | ~1,150 | ~5s | Low |
| `bias_detector` | Analysis-only, no corrective action | ~1,150 | ~5s | Low |
| `future_work` | Analysis-only, not integrated | ~1,150 | ~5s | Low |
| `comparison_table` | Orphaned output, not in main.tex | ~550 | ~4s | Moderate (bad LaTeX) |
| `formula_normalizer` | Highest token cost, highest corruption risk | ~4,500 | ~15s | **High** |
| `hallucination_guard` | Analysis-only, no corrective action | ~750 | ~4s | Low |
| `formula_verifier` | Analysis-only, redundant with normalizer | ~500 | ~4s | Low |
| `peer_reviewer` | Expensive analysis after point of no return | ~3,000 | ~12s | Low |

**Total savings:** ~12,750 tokens, ~55s wall-clock, 10 failure points eliminated.

### 6.2 Nodes to Merge (3)

| Merge | Rationale | Implementation |
|-------|-----------|----------------|
| `plan_validation` → `planner` | Planner's return dict can include `phase: "plan_validated"` directly | 4-line change to `planner_node` return |
| `workers_complete` → `worker_executor` | Worker's return already tracks task state; add phase/stop_reason | 2-line change to `make_worker_node` closure |
| `replanner` → `critic` | Critic already resets low-confidence tasks + adds recovery task. Replace replanner's LLM call with deterministic task expansion. | Add 10-line deterministic heuristic to critic: if iteration < max_iterations and low_confidence_tasks exists, add 1-2 follow-up tasks with expanded providers. Remove replanner_node entirely. |

### 6.3 Nodes to Degrade to Optional (2-3)

| Node | Flag | Default |
|------|------|---------|
| `figure_generator` | `--generate-figures` | Off (`False`) |
| `presentation` | `--presentation` | Off |
| `poster` | `--poster` | Off |

Implementation: Add `enabled_features` dict to `WorkflowState` (or reuse `GraphState`). Each optional node checks `state.get("enabled_features", {}).get("figures", False)` and returns early (phase = `{name}_skipped`) if disabled.

### 6.4 Nodes to Simplify (2)

#### `citation_verifier` 
- Remove OpenAlex auto-fix as default behavior (degrade to `--autofix-citations` flag)
- Replace per-citation parallel OpenAlex calls with a single deterministic pass: merge citation_map from combiner with item metadata
- Move unsupported-claim detection (token-overlap heuristic) into the combiner as a field on each section

#### `worker_executor`
- Merge `workers_complete` phase/stop_reason into the existing return dict
- Move the `_route_after_worker` conditional edge handling directly into the node's final state update

### 6.5 Dead Code to Remove

```
_composer.py: _build_subagent_prompt()  # Defined but never called
```

This function builds a refined prompt for scoped LLM refinement but was replaced by the single `agenerate_json` call. Remove ~20 lines.

---

## 7. Migration Strategy

### 7.1 Phase 1 (Week 1) — Low-Hanging Fruit

**Remove** `plan_validation`, `workers_complete`, `knowledge_graph`, `comparison_table`:
1. Update `build_graph()` — remove `graph.add_node("plan_validation", ...)` and add `phase: "plan_validated"` to planner's return
2. Update `build_graph()` — remove `workers_complete` node, add phase/stop_reason to worker_executor's return
3. Remove `graph.add_edge("combiner", "knowledge_graph")` → change to `graph.add_edge("combiner", "bias_detector")`
4. Remove `knowledge_graph` node from `__init__.py` imports and `__all__`
5. Remove `comparison_table` node, adjust edges: `future_work → figure_generator`
6. Remove dead `_build_subagent_prompt` from composer.py

**Validation:** Typecheck, lint, run existing tests (should still pass since these nodes don't affect core output).

### 7.2 Phase 2 (Week 2) — High-Impact Removals

**Remove** `bias_detector`, `future_work`, `formula_normalizer`, `hallucination_guard`, `formula_verifier`, `peer_reviewer`:
1. Remove all 6 nodes from graph edges
2. Connect `combiner → citation_verifier → composer → exporter` directly
3. Remove imports and `__all__` entries
4. Update `WorkflowState` / `GraphState`:
   - Remove deprecated fields (`bias_report`, `future_research_agenda`, `guard_report`, `math_verification_report`, `peer_review_report`)
   - Keep `knowledge_graph` field but mark as `@deprecated` (will be removed in Phase 3)
5. Update `exporter.py` — remove writes of deprecated report files
6. Update `from_graph_state` / `to_graph_state` — remove deprecated fields

**Validation:** Typecheck, lint, run full test suite. Some tests may need updating if they assert on removed state fields.

### 7.3 Phase 3 (Week 3) — Merges + Simplifications

**Merge** `replanner → critic`:
1. Add deterministic task-expansion logic to `critic_node` (10 lines)
2. Remove `replanner_node` from `__init__.py` and graph edges
3. Change `_route_after_critic` — remove `"replan"` path, route directly back to worker

**Simplify** `citation_verifier`:
1. Make OpenAlex auto-fix optional (config flag or state field)
2. Merge citation_map from combiner with citation extraction

**Add** `enabled_features` to `WorkflowState`:
```python
@dataclass
class WorkflowState:
    ...
    enabled_features: Dict[str, bool] = field(default_factory=lambda: {
        "figures": False,
        "presentation": False,
        "poster": False,
        "autofix_citations": False,
    })
```

**Degrade** `figure_generator`, `presentation`, `poster` to optional (check `enabled_features`).

**Validation:** Typecheck, lint, run full test suite. Verify `ret_state.from_graph_state(to_graph_state(state))` round-trips correctly.

### 7.4 Backward Compatibility Strategy

| Breaking Change | Mitigation |
|-----------------|-----------|
| Removed state fields | `from_graph_state()` uses `state.get("bias_report")` — returns `None` for old checkpoints. Safe. |
| Removed report files | Exporter skips files when field is `None`. Old checkpoints missing these fields → no crash. |
| Merged replanner | Checkpoints containing `"phase": "replanned"` will route to `"critic_scored"` → graph routes to combiner (next correct state). |

---

## 8. Before/After Comparison

| Dimension | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **Nodes** | 27 | ~16 | **41% reduction** |
| **Edges** | 28 | ~18 | **36% reduction** |
| **LLM calls** | 11 | 5 | **55% reduction** |
| **Post-processing LLM calls** | 9 | 1 (composer) | **89% reduction** |
| **Token cost (post-processing)** | ~18,700 | ~5,250 | **72% reduction** |
| **Token cost (total)** | ~21,200 | ~6,300 | **70% reduction** |
| **Wall-clock (post-processing)** | ~60-90s | ~25-35s | **58% faster** |
| **Failure surface** | 19 sequential | 11 sequential | **42% fewer S.P.O.F.** |
| **State fields** | 25+ | ~16 | **36% reduction** |
| **Analysis reports** | 6 (unused) | 0 | **100% eliminated** |
| **Dead code** | _build_subagent_prompt | removed | Clean |

---

## 9. Operational Tradeoffs

### 9.1 What We Lose

| Feature | Loss | Mitigation |
|---------|------|-----------|
| Knowledge graph visualization | KG file not generated | Add as standalone CLI command: `research-agent graph <run_id>` |
| Bias detection report | Bias not flagged | Deterministic checklist generated by exporter (institutional diversity, geographic spread) |
| Future research agenda | No extrapolation | Template-based "Future Work" section generated by composer from citation gaps |
| Comparison table | No auto-generated table | Composer can include a `/begin{tabular}` stub if citations exist |
| Math validation | No formula checking | Add regex-based validation in exporter: unbalanced brackets, unknown commands |
| Peer review | No automated review | Add as separate CLI command: `research-agent review <run_id>` |
| Formula normalization | No math notation standardization | Add deterministic regex normalization (10 lines) in exporter for common patterns |
| Figure generation | No auto-generated TikZ | Keep as optional (`--generate-figures`), off by default |
| Replanner LLM | No adaptive task generation | Critic adds deterministic follow-up tasks with expanded providers |

### 9.2 What We Gain

| Gain | Impact |
|------|--------|
| **Deterministic post-processing** | 5 of 6 remaining post-processing operations are deterministic (no LLM). Reproducible builds. |
| **Faster iteration** | 25-35s post-processing instead of 60-90s. Faster development cycles. |
| **Lower LLM latency** | Most analysis nodes use `role="orchestrator"` (local Ollama) — primary savings are wall-clock latency, not API spend. Secondary effect: reduced GPU contention. |
| **Simpler debugging** | ~16 nodes instead of 27. 11 LLM calls instead of 22. Easier to trace failures. |
| **Reduced corruption risk** | No full-document LLM replacement (formula_normalizer removed). No invalid TikZ. |
| **Stateless analysis** | Analysis reports moved out-of-band (separate CLI commands). Graph state stays focused. |

---

## 10. Simplified Graph (Final)

```
┌─────────────────────────────────────────────────────────────┐
│ START                                                        │
│   │                                                          │
│   ▼                                                          │
│ intake (deterministic)                                       │
│   │                                                          │
│   ▼                                                          │
│ clarifier (LLM: agenerate_json)                              │
│   │                                                          │
│   ├──→ await_user (if ambiguous) ──→ END                     │
│   │                                                          │
│   ▼                                                          │
│ planner + plan_validation (LLM: agenerate_json)              │
│   │                                                          │
│   ▼                                                          │
│ worker_executor + workers_complete (deterministic)           │
│   │                                                          │
│   ▼                                                          │
│ indexing (deterministic)                                     │
│   │                                                          │
│   ▼                                                          │
│ critic + replanner (deterministic heuristic)                 │
│   │                                                          │
│   ├──→ worker_executor (if low confidence) ──→ indexing ───→ │
│   │                                                          │
│   ▼                                                          │
│ combiner (LLM: agenerate_text per section)                   │
│   │                                                          │
│   ▼                                                          │
│ citation_verifier (deterministic + optional OpenAlex)        │
│   │                                                          │
│   ▼                                                          │
│ composer (LLM: agenerate_json)                               │
│   │                                                          │
│   ├──→ figure_generator (optional) ──→                       │
│   ├──→ presentation (optional) ──→                           │
│   ├──→ poster (optional) ──→                                 │
│   │                                                          │
│   ▼                                                          │
│ exporter (deterministic + validation)                        │
│   │                                                          │
│   ▼                                                          │
│ END                                                          │
└─────────────────────────────────────────────────────────────┘
```

**Core path:** intake → clarifier → planner → worker_executor → indexing → critic → combiner → citation_verifier → composer → exporter  
**Optional branches:** figure_generator, presentation, poster (run in parallel after composer)  
**Loop:** critic → worker_executor (deterministic, no LLM replanner)

---

## 11. Implementation Checklist

### Remove (10 nodes)
- [ ] `plan_validation` — merge phase into planner
- [ ] `workers_complete` — merge into worker_executor
- [ ] `replanner` — merge deterministic logic into critic
- [ ] `knowledge_graph` — remove from graph
- [ ] `bias_detector` — remove from graph
- [ ] `future_work` — remove from graph
- [ ] `comparison_table` — remove from graph
- [ ] `formula_normalizer` — remove from graph
- [ ] `hallucination_guard` — remove from graph
- [ ] `formula_verifier` — remove from graph
- [ ] `peer_reviewer` — remove from graph

### Simplify (2 nodes)
- [ ] `citation_verifier` — merge citation_map, make OpenAlex optional
- [ ] `composer` — remove dead `_build_subagent_prompt`

### Degrade to Optional (3 nodes)
- [ ] `figure_generator` — behind `--generate-figures`
- [ ] `presentation` — behind `--presentation`
- [ ] `poster` — behind `--poster`

### Clean Up (state + exporter)
- [ ] Remove deprecated `GraphState` fields
- [ ] Remove deprecated report writes from `exporter.py`
- [ ] Update `from_graph_state` / `to_graph_state`
- [ ] Add deterministic regex math normalization to exporter
- [ ] Add deterministic "future work" template to composer fallback

### Validate
- [ ] Typecheck passes
- [ ] Lint passes
- [ ] Existing tests pass (or update assertions)
- [ ] Checkpoint backward compatibility verified
- [ ] Token cost benchmark (before/after)
