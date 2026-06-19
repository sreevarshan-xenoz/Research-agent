# Document Transformation Pipeline Redesign

> **Status:** Architecture Proposal  
> **Author:** Research Agent Team  
> **Date:** 2026-05-28  

---

## 1. Executive Summary

The current document pipeline mutates a freeform LaTeX string (`latex_main`) through **5+ LLM passes**, each introducing corruption risk, token waste, and instability. This document proposes a **Structured Intermediate Representation (Paper IR)** that decouples content from rendering, enabling deterministic transformations, safe composability, and minimal LLM mutation surface.

**Primary risks eliminated:**
- Full-document LLM rewrites → Section-level structured edits
- Token explosion → Targeted, scoped LLM calls
- Hallucinated LaTeX brackets/corruption → Deterministic template rendering
- Cascading failure from early composition → Late rendering after all passes

---

## 2. Current Pipeline — Full Trace

### 2.1 Pipeline Order (after research phase completes)

```
Worker nodes → indexing_node → critic_node → replanner (loop)
                                                      ↓
combiner → knowledge_graph → bias_detector → future_work →
  comparison_table → figure_generator → citation_verifier →
    composer (⚠️ FULL DOCUMENT) → formula_normalizer (⚠️ FULL) →
      hallucination_guard → formula_verifier →
        peer_reviewer → presentation → poster → exporter
```

### 2.2 Node-by-Node Analysis

| Node | Input | LLM? | Output | Risk | Token Cost |
|------|-------|------|--------|------|------------|
| **combiner** | `task_findings` (structured) | ✅ | `combined_sections` (structured list) | Low | ~2K/task |
| **knowledge_graph** | `combined_sections[:5]` (truncated) | ✅ | `knowledge_graph` (entity JSON) | Low | ~2K |
| **bias_detector** | `task_findings` (sources) | ✅ | `bias_report` (Markdown) | Low | ~1.5K |
| **future_work** | `combined_sections[:5]` (truncated) | ✅ | `future_research_agenda` (Markdown) | Low | ~1.5K |
| **comparison_table** | `citations[:5]` | ✅ | `comparison_table` (LaTeX) | Low | ~1.5K |
| **figure_generator** | `combined_sections[:3]` (truncated) | ✅✅ | `figures` (TikZ code) | Medium | ~3.5K (2 LLM calls) |
| **citation_verifier** | `combined_sections` + `task_findings` | ❌ | `citations` + filtered sections | Low-Deterministic | 0 |
| **composer** | `combined_sections` + `figures` | ✅✅✅ | `latex_main` **FULL DOCUMENT** | **CRITICAL** | ~8-12K |
| **formula_normalizer** | `latex_main` (FULL) | ✅ | `latex_main` **FULL DOCUMENT** | **CRITICAL** | ~8-12K |
| **hallucination_guard** | `latex_main` + `combined_sections[:3]` | ✅ | `guard_report` (analysis only) | Low-Analysis | ~2K |
| **formula_verifier** | `latex_main` (regex extracts formulas) | ✅ | `math_verification_report` (analysis only) | Low-Analysis | ~1K |
| **peer_reviewer** | `latex_main` (FULL) | ✅ | `peer_review_report` (analysis only) | Low-Analysis | ~8K |
| **presentation** | `combined_sections` | ❌ | `presentation_tex` (deterministic) | Low | 0 |
| **poster** | `combined_sections` | ❌ | `poster_tex` (deterministic) | Low | 0 |
| **exporter** | All state keys | ❌ | Files on disk | Low | 0 |

---

## 3. Risk Analysis

### 3.1 Critical Risks

**Risk 1: Composer premature LaTeX rendering**

The `composer` node calls `agenerate_json()` with the full body to get title/abstract/body, then immediately calls `render_main_tex()` — locking everything into a rigid LaTeX string. This means:

- The `latex_main` is born as a fragile string
- Every subsequent node that wants to modify content must parse or regenerate LaTeX
- There is no way to safely insert the outputs of figure_generator, comparison_table, bias_report into the document without another LLM pass

**Risk 2: formula_normalizer full-document rewrite**

```python
# Current code sends the ENTIRE LaTeX document to the LLM
prompt = ("... Standardize notation in the following LaTeX draft ...\n\n"
          f"{latex_main}")  # ← 8K+ tokens sent to LLM
normalized_latex = await agenerate_text(prompt=prompt, max_tokens=4000)
```

Problems:
- The LLM must reproduce the entire document perfectly — any bracket mismatch, missing `\\end{}`, or hallucinated content corrupts the paper
- The `max_tokens=4000` is a truncation risk for long documents
- The LLM is asked to do a minor editorial task (bold vectors) but given the entire document — it will invent changes
- Token cost scales with document size, not with the task complexity

**Risk 3: No intermediate representation between analysis and rendering**

- `hallucination_guard`, `formula_verifier`, `peer_reviewer` all analyze `latex_main` by sending it to another LLM
- But there's no structured way to *apply* their findings
- If guard detects a hallucination, what fixes it? Another LLM pass on the full document!
- The analysis results are stored as Markdown reports that nobody reads programmatically

**Risk 4: Cascading corruption**

```
composer creates latex_main (high quality) →
  formula_normalizer rewrites it (may introduce errors) →
    export validates (catches some, not all bracket mismatches)
```

There is no rollback mechanism, no diff-based validation, no compilation test between passes.

### 3.2 Medium Risks

**Risk 5: figure_generator generates potentially invalid TikZ**

The figure_generator makes 2 LLM calls: one to decide what to draw, one to translate to TikZ. Both can produce invalid output. The TikZ is injected into `latex_main` during composer's `_build_body()` — if it's broken, the whole document fails.

**Risk 6: citation_verifier flags sections heuristically**

The `citation_verifier` uses token overlap heuristics (`_task_evidence_tokens`) to flag unsupported sections. It does return filtered sections via `combined_sections: filtered_sections`, so the flagging propagates — but the section content is never regenerated to remove unsupported claims. The heuristic (≥3 overlapping tokens) is coarse and may miss or over-flag legitimate citations.

**Risk 7: comparison_table generates LaTeX without integration**

The `comparison_table` returns a LaTeX `table` environment as a string. It's stored in `state["comparison_table"]` but never inserted into the final document. The user gets a separate `.tex` file.

### 3.3 Token Cost Summary

Per run (assuming 4 research sections):

| Node | Input Tokens | Output Tokens | Cost |
|------|-------------|---------------|------|
| composer | 6,000 | 4,000 | ~10,000 |
| formula_normalizer | 8,000 | 4,000 | ~12,000 |
| hallucination_guard | 4,000 | 500 | ~4,500 |
| formula_verifier | 2,000 | 500 | ~2,500 |
| peer_reviewer | 8,000 | 1,000 | ~9,000 |
| **Total waste** | **~28,000** | **~10,000** | **~38,000 tokens** |

Of these, formula_normalizer and peer_reviewer alone account for ~21,000 tokens (55%) just to read and reproduce the full document.

---

## 4. Proposed Architecture: Paper Intermediate Representation (IR)

### 4.1 Data Model

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaperSection:
    """A single section of the paper in structured form (NOT LaTeX).

    The `content` field holds plain text with embedded LaTeX math fragments
    (e.g. $\\mathbf{v}$) and inline citation reference keys (e.g. [REF1]).
    This is NOT Markdown — it is the same hybrid format currently produced
    by the combiner node. The LaTeX renderer treats content as raw text
    that may already contain \\cite{} commands and inline math.
    """
    section_id: str                    # e.g., "intro", "related_work"
    heading: str                       # Plain text heading
    content: str                       # Plain text + LaTeX fragments + [REFn] keys
    evidence_refs: list[str] = field(default_factory=list)  # citation keys e.g. ["REF1", "REF2"]
    citation_map: dict[str, dict[str, str]] = field(default_factory=dict)  # REFn → {title, url, provider}
    confidence: float = 0.0
    claims: list[str] = field(default_factory=list)         # extracted claim sentences
    subsections: list["PaperSection"] = field(default_factory=list)


@dataclass
class PaperFigure:
    """A figure with its caption and insertion anchor."""
    figure_id: str                     # e.g., "fig:architecture"
    type: str                          # "tikz" | "table" | "plot"
    content: str                       # The LaTeX/tikz code
    caption: str                       # Plain text caption
    anchor_section: str = ""           # section_id to insert after
    anchor_position: str = "after"     # "after" | "before" | "end"


@dataclass
class PaperCitation:
    """A single citation with complete metadata.

    Each citation's `key` field serves as the link between inline [REFn]
    references in PaperSection.content and the full metadata needed for
    BibTeX generation. The citation_verifier node is responsible for
    creating these keys and populating the metadata.
    """
    key: str                           # Matches \\cite{} key in rendered LaTeX
    ref_key: str = ""                  # The [REFn] string used inline in section content
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    url: str = ""
    doi: str = ""
    venue: str = ""                    # journal / conference name
    volume: str = ""
    number: str = ""
    pages: str = ""
    publisher: str = ""
    entry_type: str = "misc"          # BibTeX entry type


@dataclass
class PaperEquation:
    """An equation that should appear in the paper."""
    equation_id: str                   # e.g., "eq:loss"
    latex: str                         # LaTeX equation content (no \begin{equation})
    anchor_section: str = ""
    label: str = ""


@dataclass
class AnalysisReport:
    """A non-mutating analysis result attached to the paper."""
    report_type: str                   # "hallucination" | "peer_review" | "math_verify" | "bias"
    content: str                       # Markdown report
    severity: str = "info"             # "info" | "warning" | "critical"
    affected_sections: list[str] = field(default_factory=list)


@dataclass
class PaperDocument:
    """
    Structured intermediate representation of the entire paper.
    All LLM-driven operations work on this structure.
    LaTeX is rendered ONCE at the end by the exporter.
    """
    title: str = ""
    abstract: str = ""
    sections: list[PaperSection] = field(default_factory=list)
    citations: list[PaperCitation] = field(default_factory=list)
    figures: list[PaperFigure] = field(default_factory=list)
    equations: list[PaperEquation] = field(default_factory=list)
    analyses: list[AnalysisReport] = field(default_factory=list)
    language: str = "en"
    template: str = "ieee"
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_section(self, section_id: str) -> PaperSection | None:
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None

    def get_ordered_content(self) -> list[PaperSection | PaperFigure | PaperEquation]:
        """Returns sections, figures, equations interleaved by anchor sections."""
        items: list[PaperSection | PaperFigure | PaperEquation] = []
        for section in self.sections:
            items.append(section)
            for fig in self.figures:
                if fig.anchor_section == section.section_id:
                    items.append(fig)
            for eq in self.equations:
                if eq.anchor_section == section.section_id:
                    items.append(eq)
        return items
```

### 4.2 Pipeline State Changes

| Current State Key | New State Key | Type | Notes |
|-------------------|---------------|------|-------|
| `combined_sections` | `paper.sections` | `list[PaperSection]` | Transitional — can be removed after migration |
| `citations` | `paper.citations` | `list[PaperCitation]` | |
| `figures` | `paper.figures` | `list[PaperFigure]` | |
| `latex_main` | ❌ REMOVED | — | Replaced by final `render_latex(paper)` call |
| `guard_report` | `analyses[hallucination]` | `AnalysisReport` | |
| `math_verification_report` | `analyses[math]` | `AnalysisReport` | |
| `peer_review_report` | `analyses[peer_review]` | `AnalysisReport` | |
| `bias_report` | `analyses[bias]` | `AnalysisReport` | |

New state key:
- `paper: PaperDocument` — single source of truth for document content

---

## 5. Node-by-Node Migration Plan

### 5.1 Phase 1: Introduce PaperDocument (Low Risk)

**Changes:**
1. Add `PaperDocument` and associated types to `state.py`
2. Add `paper` to `GraphState` as `dict[str, Any]` (serializable)
3. Update `from_graph_state` / `to_graph_state` serialization helpers
4. Add `render_latex(paper: PaperDocument) -> str` to `renderer.py`

**Migration adapter:**
```python
# Temporary bridge — to be removed in Phase 3
def paper_from_combined_sections(
    state: GraphState,
) -> PaperDocument:
    return PaperDocument(
        sections=[
            PaperSection(
                section_id=s.get("task_id", f"sec_{i}"),
                heading=s.get("heading", ""),
                content=s.get("content", ""),
                evidence_refs=list(s.get("citation_map", {}).keys()),
            )
            for i, s in enumerate(state.get("combined_sections", []))
        ],
        citations=[
            PaperCitation(**c) for c in state.get("citations", [])
        ],
        ...
    )
```

### 5.2 Phase 2: Analysis-Only Nodes Stay, Mutating Nodes Move to Paper IR

| Node | Action | New behavior |
|------|--------|-------------|
| **combiner** | Update output | Output `PaperSection` list instead of `combined_sections` |
| **knowledge_graph** | No change | Already analysis-only |
| **bias_detector** | No change | Already analysis-only |
| **future_work** | No change | Already analysis-only |
| **comparison_table** | Update to `PaperFigure` | Output a `PaperFigure(type="table")` |
| **figure_generator** | Update to `PaperFigure` | Output `PaperFigure` objects directly |
| **citation_verifier** | Update to read `paper` | Analyze `PaperDocument`, output warnings |
| **composer** | **Rewrite (deterministic)** | No LLM call. Assembles `PaperDocument` from sections + figures. Renders LaTeX once via `render_latex()`. |
| **formula_normalizer** | **Rewrite (section-level)** | Process each `PaperSection.content` individually via LLM. Validate output before committing. |
| **hallucination_guard** | No change | Already analysis-only. Update to read PaperDocument instead of `latex_main`. |
| **formula_verifier** | No change | Already analysis-only. Read equations from PaperDocument. |
| **peer_reviewer** | No change | Already analysis-only. Read sections from PaperDocument. |
| **presentation** | Update | Read PaperDocument instead of `combined_sections` |
| **poster** | Update | Read PaperDocument instead of `combined_sections` |
| **exporter** | **Major rewrite** | Call `render_latex()` once to produce `latex_main`. Validate compiled output. |

### 5.3 Phase 3: Remove `latex_main` from State

- Remove `latex_main` from `GraphState`
- All downstream nodes that read `latex_main` now read `PaperDocument`
- The only time LaTeX is produced is in the exporter node
- Add LaTeX compilation smoke test in exporter (``tectonic`` or ``pdflatex`` with timeout)

---

## 6. Detailed Node Redesigns

### 6.1 Composer Redesign (Deterministic)

**Current (unsafe):**
```python
# Sends entire combined body to LLM, gets back JSON with body
composed_json = await agenerate_json(prompt=prompt)
body = composed_json.get("body", fallback_body)
latex_main = render_main_tex(body=body, ...)
```

**Proposed (deterministic):**
```python
def composer_node(state: GraphState) -> dict:
    paper = state.get("paper") or paper_from_combined_sections(state)
    
    # Deterministic assembly — NO LLM CALL
    paper.title = state.get("topic")  # Or from task refinement
    paper.abstract = _build_abstract(paper.sections)
    
    # Only LLM call: refine title/abstract from structured data (scoped)
    refined = await agenerate_json(
        prompt=f"Given these sections: {_summarize_sections(paper.sections)}\n"
               f"Generate a compelling title and abstract for the paper.",
        max_tokens=500  # Much smaller scope
    )
    if refined:
        paper.title = refined.get("title", paper.title)
        paper.abstract = refined.get("abstract", paper.abstract)
    
    return {"paper": paper, "phase": "composed"}
```

Key changes:
- `PaperDocument` is assembled deterministically from sections/figures/citations
- The only LLM call is for title/abstract generation — a small, scoped task
- No LLM rewrites the body

### 6.2 Formula Normalizer Redesign (Section-Level, Validated)

**Current (unsafe):**
```python
# Sends entire LaTeX document to LLM
prompt = f"{latex_main}"
normalized_latex = await agenerate_text(prompt=prompt, max_tokens=4000)
```

**Proposed (section-level, validated):**
```python
import re

def _normalize_whitespace(latex: str) -> str:
    """Collapse multiple spaces and normalize braces for fuzzy matching."""
    latex = re.sub(r'\\s+', ' ', latex)
    latex = latex.strip()
    return latex

async def formula_normalizer_node(state: GraphState) -> dict:
    paper: PaperDocument = state["paper"]
    warnings = []
    
    for section in paper.sections:
        formulas = extract_latex_formulas(section.content)
        if not formulas:
            continue
        
        # Only send extracted formulas, not the full section
        prompt = (
            "Standardize these LaTeX formulas:\n"
            f"{chr(10).join(formulas)}\n\n"
            "Rules:\n"
            "1. Vectors: \\mathbf{{v}}\n"
            "2. Matrices: \\mathbf{{A}}\n"
            "3. Output the corrected formulas only, one per line.\n"
            "4. Preserve ALL whitespace and line breaks EXACTLY as in the input."
        )
        
        fixed_formulas_text = await agenerate_text(prompt=prompt, max_tokens=500)
        fixed_formulas = fixed_formulas_text.strip().split("\n")
        
        if len(fixed_formulas) != len(formulas):
            warnings.append(
                f"Section {section.section_id}: formula count mismatch "
                f"({len(formulas)} input vs {len(fixed_formulas)} output)"
            )
            continue
        
        # Apply replacements with fuzzy matching + bracket validation
        for old, new in zip(formulas, fixed_formulas):
            if not _validate_bracket_balance(new):
                warnings.append(f"Section {section.section_id}: bracket mismatch in "
                                f"'{new[:50]}...' — skipping")
                continue
            
            # Fuzzy match: try normalized exact match first, then whitespace-agnostic
            if old in section.content:
                section.content = section.content.replace(old, new, 1)
            elif _normalize_whitespace(old) in _normalize_whitespace(section.content):
                # Fallback: normalize whitespace before replacing
                norm_old = _normalize_whitespace(old)
                norm_new = _normalize_whitespace(new)
                section.content = re.sub(
                    re.escape(norm_old), norm_new, section.content, count=1
                )
            else:
                warnings.append(f"Section {section.section_id}: formula not found in content "
                                f"— cannot apply normalization")
    
    return {"paper": paper, "run_warnings": state.get("run_warnings", []) + warnings}
```

Key changes:
- Processes formulas extracted via regex, not the full document
- Fuzzy matching with whitespace normalization handles LLM formatting drift
- Validates bracket balance before each replacement
- Rejects invalid replacements rather than corrupting the document
- Token cost: O(formulas × 200) instead of O(document × 8000)

### 6.3 Exporter Redesign (Late Rendering + Compilation)

**Current:**
```python
# Takes pre-rendered latex_main from state
export_run_artifacts(main_tex=state["latex_main"])
```

**Proposed:**
```python
async def exporter_node(state: GraphState) -> dict:
    paper: PaperDocument = state["paper"]
    
    # RENDER ONCE — deterministic from PaperDocument
    latex_main = render_latex(paper)
    bibtex = build_bibtex(paper.citations)
    
    # Validate before writing
    errors = validate_latex_package(latex_main, bibtex)
    if errors:
        return {"phase": "validation_failed", "run_warnings": errors}
    
    # Attempt compilation as smoke test
    compile_result = await try_compile(latex_main, bibtex)
    if compile_result.pdf_path:
        paper.metadata["pdf_compiled"] = True
    
    # Write artifacts
    artifact_dir = export_run_artifacts(main_tex=latex_main, bibtex=bibtex, ...)
    return {"phase": "completed", "artifact_dir": artifact_dir}
```

### 6.4 Analysis Nodes (Minimal Changes)

Analysis-only nodes (hallucination_guard, formula_verifier, peer_reviewer) need minimal changes:
- Read from `paper.sections` instead of `latex_main`
- Output `AnalysisReport` to `paper.analyses`
- Don't mutate the document

```python
async def hallucination_guard_node(state: GraphState) -> dict:
    paper: PaperDocument = state["paper"]
    
    # Use first 3 sections for analysis (same as before)
    context = "\n".join([
        f"Section: {s.heading}\nContent: {s.content[:1000]}"
        for s in paper.sections[:3]
    ])
    
    report = await agenerate_text(prompt=..., context=context)
    
    analysis = AnalysisReport(
        report_type="hallucination",
        content=report,
        severity="warning" if "No hallucinations" not in (report or "") else "info",
    )
    paper.analyses.append(analysis)
    
    return {"paper": paper, "phase": "guard_complete"}
```

---

## 7. Validation and Safety Guarantees

### 7.1 Deterministic LaTeX Rendering

`render_latex()` takes a `PaperDocument` and produces a LaTeX string. It:

1. Iterates sections in order, rendering each to `\section{}` + body
2. Inserts figures at their anchor positions
3. Inserts equations at their anchor positions
4. Wraps everything in the chosen template (IEEE, ACM, etc.)
5. Escapes special characters deterministically

**No LLM involvement in LaTeX generation.** This means:
- Bracket balance is guaranteed by the template
- No hallucinated `\end{document}` or missing packages
- Token cost: 0 for LaTeX generation

### 7.2 Section-Level Validation

Each LLM operation on a section is validated:
- **Bracket balance**: `\begin{...}` count == `\end{...}` count
- **Token limit**: Section content has a max token budget
- **Replace count**: Formula normalizer verifies same number of replacements

### 7.3 Compilation Smoke Test

The exporter attempts to compile the generated LaTeX:
- `tectonic main.tex` (if available)
- Falls back to basic marker validation
- On compilation failure: logs error but still exports source (user can fix manually)

### 7.4 Rollback on Failure

If any mutating node fails validation:
- The previous state of that section is preserved
- A warning is added to `run_warnings`
- Execution continues with the unmodified section

---

## 8. Migration Strategy

### 8.1 Phase 1: PaperDocument + Dual State (Week 1)

**Goal:** Introduce PaperDocument without breaking existing behavior.

```
1. Add PaperDocument types to state.py
2. Add paper field to GraphState (backward-compat: optional, defaults to empty dict)
3. Add render_latex() to renderer.py
4. Add paper_from_combined_sections() bridge function
5. Add paper state to all references in state.py helpers
6. Tests: verify round-trip serialization, render_latex produces valid LaTeX
```

**Risk:** Low. No existing code is changed — new types are additive.

### 8.1a Checkpoint Compatibility Note

During Phase 1, `GraphState` gains an optional `paper` key. Existing checkpoints
saved with `MemorySaver` or `AsyncRedisSaver` will **not** have this key. All
code that reads `state["paper"]` must fall back to the bridge function:

```python
def _get_paper(state: GraphState) -> PaperDocument:
    if "paper" in state and state["paper"]:
        return PaperDocument.from_dict(state["paper"])  # type: ignore[arg-type]
    return paper_from_combined_sections(state)  # type: ignore[arg-type]
```

This ensures that:
- New runs start with `paper` populated by the combiner
- Resumed runs from old checkpoints transparently reconstruct PaperDocument
- The bridge function can be removed in Phase 3 when all checkpoints are migrated

### 8.2 Phase 2: Migrate Mutating Nodes (Week 2)

**Goal:** Move composer and formula_normalizer to PaperDocument.

```
1. Rewrite composer_node to assemble PaperDocument deterministically
2. Rewrite formula_normalizer_node to operate section-level
3. Update exporter_node to call render_latex()
4. Tests: verify output matches existing behavior for known inputs
5. Run full pipeline with PaperDocument, compare output LaTeX with current output
```

**Risk:** Medium. Composer behavior changes — title/abstract generation becomes scoped.

### 8.3 Phase 3: Remove Legacy State (Week 3)

**Goal:** Remove latex_main and combined_sections from state.

```
1. Remove combined_sections, latex_main, bibtex, figures from GraphState
2. Remove paper_from_combined_sections() bridge function and _get_paper() fallback
3. Update all remaining analysis nodes to read PaperDocument
4. Update presentation/poster generators to read PaperDocument
5. Clean up unused imports and dead code
6. Full regression test suite
```

**Risk:** Medium. Changes touch many files, but are mechanical.

---

## 9. Operational Recommendations

### 9.1 Token Savings Estimate

| Current | Proposed | Savings |
|---------|----------|---------|
| composer: ~10K tokens | composer: ~500 tokens (title only) | **95%** |
| formula_normalizer: ~12K tokens | formula_normalizer: ~1K tokens (formulas only) | **92%** |
| peer_reviewer: ~9K tokens | peer_reviewer: ~9K (unchanged) | **0%** |
| hallucination_guard: ~4.5K | hallucination_guard: ~4.5K (unchanged) | **0%** |
| **Total per run: ~38K tokens** | **Total per run: ~16.5K tokens** | **~57% reduction** |

### 9.2 Stability Improvements

1. **No full-document LLM mutation** — The most common source of LaTeX corruption is eliminated
2. **Deterministic LaTeX generation** — Templates guarantee structural correctness
3. **Section-level validation** — Isolated failures don't corrupt the entire document
4. **Compilation smoke test** — Catches errors before the user opens the PDF
5. **Graceful degradation** — Failed sections keep their previous content instead of blank pages

### 9.3 Monitoring Metrics

Add these counters to the observability layer:

1. **`pipeline.latex_compile_success_rate`** — % of runs where tectonic compilation succeeds
2. **`pipeline.section_mutation_count`** — # of sections modified by formula_normalizer
3. **`pipeline.validation_bracket_failures`** — # of bracket mismatches caught by validators
4. **`pipeline.token_savings`** — Actual vs. estimated token usage before/after migration

---

## 10. Summary of Changes per File

| File | Phase | Change |
|------|-------|--------|
| `orchestration/state.py` | 1 | Add `PaperDocument`, `PaperSection`, `PaperFigure`, `PaperCitation`, `PaperEquation`, `AnalysisReport` |
| `orchestration/state.py` | 1 | Add `paper` to `GraphState` + serialization helpers |
| `output/latex/renderer.py` | 1 | Add `render_latex(paper: PaperDocument) -> str` |
| `orchestration/nodes/composer.py` | 2 | Rewrite: deterministic assembly, scoped title/abstract LLM |
| `orchestration/nodes/formula_normalizer.py` | 2 | Rewrite: section-level, validated, bracket-balanced |
| `orchestration/nodes/exporter.py` | 2 | Late rendering via `render_latex()`, add compilation smoke test |
| `orchestration/nodes/hallucination_guard.py` | 3 | Read `paper.sections` instead of `latex_main` |
| `orchestration/nodes/formula_verifier.py` | 3 | Read `paper.equations` instead of regex on `latex_main` |
| `orchestration/nodes/peer_reviewer.py` | 3 | Read `paper.sections` instead of `latex_main` |
| `orchestration/nodes/figure_generator.py` | 2 | Output `PaperFigure` objects |
| `orchestration/nodes/comparison_table.py` | 2 | Output `PaperFigure(type="table")` |
| `orchestration/nodes/combiner.py` | 2 | Output `PaperSection` list |
| `orchestration/nodes/presentation.py` | 3 | Read `paper.sections` |
| `orchestration/nodes/poster.py` | 3 | Read `paper.sections` |
| `orchestration/graph.py` | 3 | Remove `latex_main` edges, update builder |
| `output/exporter.py` | 2 | Accept `PaperDocument` and call `render_latex()` |

---

## 11. Appendix: LaTeX Template Integration

The `render_latex()` function uses the existing Jinja2 templates but receives structured data:

```python
def render_latex(paper: PaperDocument) -> str:
    env = _get_jinja_env()
    template = env.get_template(f"{paper.template}/main.tex.j2")
    
    body_parts = []
    for item in paper.get_ordered_content():
        if isinstance(item, PaperSection):
            body_parts.append(_render_section(item))
        elif isinstance(item, PaperFigure):
            body_parts.append(_render_figure(item))
        elif isinstance(item, PaperEquation):
            body_parts.append(_render_equation(item))
    
    return template.render(
        title=escape_latex(paper.title),
        abstract=escape_latex(paper.abstract),
        body="\n\n".join(body_parts),
        ...
    )
```

Each renderer is a pure function with no LLM involvement:

```python
def _render_section(section: PaperSection) -> str:
    parts = []
    parts.append(f"\\section{{{escape_latex(section.heading)}}}")
    parts.append(section.content)  # Already contains LaTeX citations [REF1], etc.
    
    for sub in section.subsections:
        parts.append(f"\\subsection{{{escape_latex(sub.heading)}}}")
        parts.append(sub.content)
    
    return "\n".join(parts)
```

This ensures:
- Every `\section` is properly opened and closed
- No missing `\end{document}`
- All special characters are escaped
- Figures and equations are positioned correctly
