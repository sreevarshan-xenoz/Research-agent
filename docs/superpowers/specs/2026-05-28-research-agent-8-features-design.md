# Research Agent — 8-Feature Enhancement Design

> Generated: May 28, 2026
> Status: Approved
> Scope: 8 new features for the Research Agent pipeline

---

## Feature Summary

| # | Feature | Type | Impact |
|---|---------|------|--------|
| R1 | Paper-to-Blog Generator | Differentiator | High |
| R2 | Interactive LaTeX Preview | QoL | High |
| R3 | Research Q&A Chatbot | Differentiator | High |
| R4 | Research Gap Finder | Differentiator | High |
| R5 | Dataset Discovery | Differentiator | Medium |
| R6 | Citation Network Visualization | Differentiator | Medium |
| R7 | Grant Proposal Generator | Differentiator | High |
| R8 | Plagiarism Checker | QoL | High |

---

## R1: Paper-to-Blog Generator

### Purpose
Convert completed research paper output into dissemination formats: blog post, newsletter summary, and Twitter/X thread.

### Architecture
```
[Completed Run] → [LaTeX Parser] → [Section Extractor] → [Blog Generator] → [Export]
                      ↓                   ↓                      ↓
                  main.tex          Abstract, Intro,        LLM call with
                                    Results, Conclusion     format-specific
                                                           prompt templates
```

### Components
- `src/research_agent/output/blog_generator.py` — orchestrator
- `src/research_agent/output/templates/` — Jinja2 templates for blog/newsletter/thread
- API: `POST /api/runs/{run_id}/export/blog`

### Data Flow
1. User requests blog export on completed run
2. System extracts structured sections from `main.tex` (title, abstract, methodology, results, conclusion)
3. Feed sections + peer review report to LLM with format-specific prompt
4. LLM generates Markdown blog, newsletter, or tweet thread
5. Write to `artifacts/<run_id>/blog/` as `.md` files
6. Return download links or display in UI

### Output Formats
- **Blog post**: Markdown, SEO-optimized, proper headings, code blocks
- **Newsletter**: 1-2 paragraphs, executive summary style
- **Twitter thread**: 5-10 tweets with key findings, stats, hook

### Error Handling
- LaTeX parsing failure → fall back to raw text extraction
- LLM unavailable → template-based summarization (deterministic)
- Twitter API rate limiting → queue and retry

### Testing
- Unit: LaTeX parser, template rendering
- Integration: Full pipeline from `main.tex` to `.md` output
- Snapshot tests for blog format consistency

---

## R2: Interactive LaTeX Preview

### Purpose
Render LaTeX output as viewable PDF in the browser without requiring local compilation.

### Architecture
```
[main.tex] → [LaTeX Compiler] → [PDF] → [PDF.js Viewer] → [Browser]
                ↓                                ↓
          Server-side                    In-browser preview
          tectonic/Docker                with zoom, search
```

### Components
- `src/research_agent/output/pdf_renderer.py` — LaTeX compilation wrapper
- `src/research_agent/app/static/js/pdf-viewer.js` — PDF.js integration
- API:
  - `POST /api/runs/{run_id}/render` — compile LaTeX to PDF
  - `GET /api/runs/{run_id}/render/pdf` — serve compiled PDF
  - `GET /api/runs/{run_id}/render/status` — compilation status

### Compilation Strategy
| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| tectonic | Standalone Rust binary | Fast, no Docker, reliable | Requires install |
| Docker | texlive image | Full LaTeX support | Heavy, slow startup |
| Client-side | MathJax/KaTeX | Zero server load | Limited, no figures |

Primary: tectonic. Fallback: Docker. Quick preview: client-side.

### Data Flow
1. User clicks "Preview" on completed run
2. Check if PDF cached in `artifacts/<run_id>/main.pdf`
3. If not cached: compile with tectonic → Docker fallback → error
4. Serve PDF via API endpoint
5. Frontend renders with PDF.js: full page view, zoom, search, page navigation, download

### Caching
- PDF cached after first compilation
- Re-compilation on: new run, manual re-render, template change

### Error Handling
- tectonic not installed → installation instructions + Docker fallback
- LaTeX compilation error → error log with line numbers
- PDF too large (>10MB) → warn, offer compressed version
- Timeout (>60s) → cancel, offer download of raw `.tex`

### Testing
- Unit: PDF renderer, cache lookup
- Integration: Known `.tex` → compile → verify PDF
- E2E: Render → preview in browser → verify zoom/search

---

## R3: Research Q&A Chatbot

### Purpose
Upload PDF papers and ask natural language questions with citation-backed answers.

### Architecture
```
[PDF Upload] → [Parser] → [Chunker] → [Embedder] → [Qdrant Index]
                                                         ↓
[User Question] → [Query Embedder] → [Qdrant Search] → [LLM Answer + Citations]
```

### Components
- `src/research_agent/chat/parser.py` — PDF extraction via PyMuPDF
- `src/research_agent/chat/chunker.py` — semantic chunking with overlap
- `src/research_agent/chat/indexer.py` — Qdrant upsert
- `src/research_agent/chat/ask.py` — query + answer generation
- API:
  - `POST /api/chat/upload` — upload PDF, returns library_id
  - `POST /api/chat/ask` — question + library_id, returns answer + citations
  - `GET /api/chat/library` — list uploaded papers

### Data Flow
1. User uploads PDF via API or UI
2. Parser extracts text + metadata (title, authors, abstract)
3. Chunker splits into ~512-token chunks with 50-token overlap
4. Embeddings generated (local sentence-transformers or NVIDIA API)
5. Stored in Qdrant collection `chat_<library_id>`
6. Question → query embedded → top-k chunks retrieved → LLM generates answer with `[1]` citations

### Key Decisions
- Collection per library: isolated, deletable, multi-user
- Reuses existing Qdrant infrastructure
- Citation format: `[#]` references linking to source PDF + page number
- Configurable limits: 50MB per PDF, 100 papers per library

### Error Handling
- Corrupted PDF → skip, report error with filename
- Empty text extraction → flag as scanned PDF, suggest OCR
- Qdrant down → in-memory NumPy fallback

### Testing
- Unit: PDF parser, chunker, citation formatter
- Integration: Upload → ask → verify answer references correct source
- E2E: 3+ papers, verify cross-document answers

---

## R4: Research Gap Finder

### Purpose
Analyze papers on a topic and identify what's NOT covered: methodology gaps, unexplored populations, missing comparisons, open questions.

### Architecture
```
[Topic/Papers] → [Worker Pass] → [Gap Analysis Node] → [Gap Report]
                      ↓                    ↓
               Existing evidence      LLM reasoning about
               from Qdrant index      what's missing
```

### Components
- `src/research_agent/orchestration/nodes/gap_analyzer.py` — pipeline node
- `src/research_agent/output/gap_report.py` — formats findings
- API: `GET /api/runs/{run_id}/gaps`

### Gap Detection Strategies
| Strategy | Method |
|----------|--------|
| Methodology gaps | Compare methods across papers — what's never tried? |
| Population gaps | Extract study populations — who's underrepresented? |
| Temporal gaps | Check citation recency — recent findings ignored? |
| Contradiction gaps | Papers that disagree but don't address each other |
| Evaluation gaps | Compare metrics — what important ones are missing? |
| Scope gaps | Subtopics mentioned but never deeply explored |

### Data Flow
1. After run completes (or on demand), gap analyzer runs
2. Retrieve all evidence chunks from Qdrant
3. Group by methodology, population, evaluation metrics
4. LLM analyzes grouped evidence for missing patterns
5. Generate gap report: categorized gaps with confidence scores
6. Save to `artifacts/<run_id>/gap_analysis.md` + `.json`

### Output Format
```json
{
  "gaps": [
    {
      "category": "methodology",
      "description": "No studies use longitudinal design",
      "confidence": 0.85,
      "related_papers": ["paper1.pdf", "paper2.pdf"],
      "suggested_research": "A longitudinal study tracking..."
    }
  ]
}
```

### Integration
- Auto-trigger after critic loop (low confidence = more gaps)
- Feeds R7 (Grant Proposal) — gaps justify proposed research
- Feeds R1 (Blog) — "future directions" section

### Error Handling
- Too few papers (<5) → "insufficient data" + recommendation
- LLM unavailable → rule-based gap detection (keyword/pattern matching)

### Testing
- Unit: Each gap detection strategy independently
- Integration: Known gap in test corpus → verify detected
- Validation: Expert review of gap reports

---

## R5: Dataset Discovery

### Purpose
Find relevant datasets from HuggingFace and Kaggle matching the research topic.

### Architecture
```
[Research Topic] → [Query Builder] → [HuggingFace API] ─┐
                    ↓                                    ├──→ [Dedup & Rank] → [Report]
                 [Query Builder] → [Kaggle API] ────────┘
```

### Components
- `src/research_agent/tools/huggingface.py` — HuggingFace Hub API adapter
- `src/research_agent/tools/kaggle.py` — Kaggle API adapter
- `src/research_agent/orchestration/nodes/dataset_finder.py` — pipeline node
- API: `GET /api/runs/{run_id}/datasets`

### API Details
| Provider | Endpoint | Auth | Rate Limit |
|----------|----------|------|------------|
| HuggingFace | `GET /api/datasets?search=...` | None (public) | 100 req/min |
| Kaggle | `GET /api/v1/datasets/list?search=...` | API key (optional) | Free tier |

### Data Flow
1. Extract key terms from topic + generated sections
2. Query HuggingFace: dataset search by tags, task, keywords
3. Query Kaggle: dataset search by topic, size, votes
4. Deduplicate by name + size + overlapping columns
5. Rank by: download count, recency, relevance score
6. Output dataset report

### Output Format
```json
{
  "datasets": [
    {
      "name": "squad",
      "provider": "huggingface",
      "description": "Reading Comprehension Dataset",
      "size": "335 MB",
      "downloads": 150000,
      "relevance": 0.82,
      "url": "https://huggingface.co/datasets/squad",
      "suggested_use": "Evaluate reading comprehension models"
    }
  ]
}
```

### Error Handling
- API down → skip provider, continue with others
- No results → "try broadening search terms"
- Kaggle not configured → skip gracefully

### Testing
- Unit: Query builder, dedup logic, ranking
- Integration: Mock API responses → verify output format
- E2E: Known topic → verify datasets found

---

## R6: Citation Network Visualization

### Purpose
Interactive graph showing how papers cite each other. Nodes = papers, edges = citations.

### Architecture
```
[Citation Data] → [Graph Builder] → [D3.js/React-Force] → [Interactive UI]
                      ↓                    ↓
               OpenAlex citation     Force-directed layout
               links + references    with zoom, click, filter
```

### Components
- `src/research_agent/orchestration/nodes/citation_graph.py` — builds graph
- `src/research_agent/output/citation_graph.py` — exports JSON for frontend
- Frontend: `static/js/citation-graph.js` — D3.js visualization
- API: `GET /api/runs/{run_id}/citation-graph`

### Graph Data Model
```json
{
  "nodes": [
    {
      "id": "paper_abc123",
      "title": "Attention Is All You Need",
      "authors": ["Vaswani et al."],
      "year": 2017,
      "citations": 90000,
      "relevance": 0.95,
      "section": "related_work"
    }
  ],
  "edges": [
    {
      "source": "paper_abc123",
      "target": "paper_def456",
      "type": "cites",
      "weight": 1.0
    }
  ]
}
```

### Visualization Features
- Force-directed layout (papers cluster by topic/citation density)
- Node sizing by citation count (influence)
- Color coding by year, section, or relevance
- Hover tooltip: title, authors, year, abstract snippet
- Click: expand node with full metadata
- Filter: year range, minimum citations, topic
- Zoom/pan for large graphs
- Export as PNG/SVG

### Data Flow
1. After run, citation graph node extracts papers + citation links
2. Build adjacency list with metadata
3. Export as D3-compatible JSON
4. Frontend renders force-directed graph
5. User interacts: filter, expand, export

### Error Handling
- No citations → message + "expand search" option
- Too many nodes (>500) → aggressive clustering, summary view
- OpenAlex down → use internal citation data only

### Testing
- Unit: Graph builder, JSON serialization
- Integration: Known network → verify node/edge counts
- Visual: Snapshot tests for frontend rendering

---

## R7: Grant Proposal Generator

### Purpose
Produce draft grant proposal sections for NSF, NIH, ERC using research output.

### Architecture
```
[Research Output] → [Template Selector] → [Section Generator] → [Proposal Draft]
                         ↓                      ↓
                    Agency-specific         LLM with structured
                    templates (NSF/NIH)     prompts per section
```

### Components
- `src/research_agent/output/grant_proposal.py` — orchestrator
- `src/research_agent/output/templates/grants/` — Jinja2 per agency
  - `nsf_template.md.j2`
  - `nih_template.md.j2`
  - `erc_template.md.j2`
- API: `POST /api/runs/{run_id}/export/grant`

### Proposal Sections
| Section | Source |
|---------|--------|
| Title | Paper title + keywords |
| Abstract | Paper abstract adapted for funding |
| Problem Statement | Gap analysis + motivation |
| Literature Review | Paper's related work |
| Methodology | Paper's methodology |
| Expected Outcomes | Conclusions + future work |
| Budget Justification | Template-based |
| Timeline | Template-based (3-5 year) |
| Broader Impacts | LLM-generated from topic + gaps |

### Template Differences
| Agency | Focus | Tone |
|--------|-------|------|
| NSF | Broader impacts, education, diversity | Collaborative, societal benefit |
| NIH | Clinical relevance, translational | Medical, patient outcomes |
| ERC | Scientific excellence, frontier | Ambitious, high-risk/high-reward |

### Data Flow
1. User selects agency + run
2. Load agency-specific template
3. Extract sections from paper + gap analysis + peer review
4. Feed to LLM with agency-specific prompt
5. Generate sections with template placeholders
6. Output Markdown + optional LaTeX
7. Save to `artifacts/<run_id>/grant_proposal_<agency>.md`

### Error Handling
- No paper generated → prompt to run research first
- LLM unavailable → templates with placeholder text + paper sections
- Unsupported agency → error with supported list

### Testing
- Unit: Template rendering, section extraction
- Integration: Full run → grant proposal → verify sections populated
- Validation: Compare to funded examples

---

## R8: Plagiarism Checker

### Purpose
Detect unintentional overlap between generated content and source papers. Report similarity scores and suggest rewrites.

### Architecture
```
[Generated Paper] → [Passage Extractor] → [Similarity Search] → [Overlap Report]
                           ↓                      ↓
                      Sliding window         Cosine similarity
                      (sentence-level)       against source chunks
```

### Components
- `src/research_agent/verification/plagiarism_checker.py` — core checker
- `src/research_agent/verification/rewrite_suggester.py` — paraphrase suggestions
- API: `POST /api/runs/{run_id}/plagiarism-check`

### Detection Methods
| Method | How | Catches |
|--------|-----|---------|
| Cosine similarity | Embed sentences, compare to source chunks | Paraphrased content |
| N-gram overlap | Exact 5-8 gram matching | Copied phrases |
| Structural similarity | Compare section structure | Lifted organization |
| Citation verification | Check cited content vs actual paper | Misattributed claims |

### Data Flow
1. User triggers check on completed run
2. Extract all sentences from `main.tex`
3. For each sentence:
   - Embed with sentence-transformers
   - Search Qdrant for top-5 similar source chunks
   - Calculate cosine similarity
   - Check n-gram overlap
4. Flag sentences with similarity > 0.8 (configurable)
5. Generate overlap report

### Output Format
```json
{
  "overall_score": 0.92,
  "flagged_sentences": [
    {
      "text": "The transformer architecture revolutionized NLP...",
      "source": "Vaswani et al. 2017, page 3",
      "similarity": 0.87,
      "type": "paraphrase",
      "suggested_rewrite": "A major advancement in NLP came with..."
    }
  ],
  "statistics": {
    "total_sentences": 150,
    "flagged": 8,
    "exact_matches": 2,
    "paraphrases": 6
  }
}
```

### Rewrite Suggestions
- Paraphrased: 2-3 alternative phrasings via LLM
- Exact matches: High priority flag, suggest citation or rewrite
- Structural overlap: Suggest section reorganization

### Error Handling
- No sources → check only against web (DuckDuckGo snippets)
- Qdrant down → in-memory NumPy similarity
- Too many sentences → batch processing with progress

### Testing
- Unit: Similarity calculation, n-gram matching
- Integration: Known overlap → verify detected at threshold
- False positive: Original content → verify NOT flagged

---

## Cross-Cutting Concerns

### Shared Dependencies
- **Qdrant**: Used by R3 (chat), R4 (gaps), R6 (citations), R8 (plagiarism)
- **sentence-transformers**: Used by R3, R4, R8 for embeddings
- **PyMuPDF**: Used by R2 (PDF parsing), R3 (upload parsing)
- **LLM**: Used by R1, R3, R4, R7 for generation
- **Jinja2**: Used by R1, R7 for templates

### API Additions Summary
| Endpoint | Feature |
|----------|---------|
| `POST /api/runs/{run_id}/export/blog` | R1 |
| `POST /api/runs/{run_id}/render` | R2 |
| `GET /api/runs/{run_id}/render/pdf` | R2 |
| `POST /api/chat/upload` | R3 |
| `POST /api/chat/ask` | R3 |
| `GET /api/chat/library` | R3 |
| `GET /api/runs/{run_id}/gaps` | R4 |
| `GET /api/runs/{run_id}/datasets` | R5 |
| `GET /api/runs/{run_id}/citation-graph` | R6 |
| `POST /api/runs/{run_id}/export/grant` | R7 |
| `POST /api/runs/{run_id}/plagiarism-check` | R8 |

### New File Tree
```
src/research_agent/
├── chat/                          # R3: Q&A Chatbot
│   ├── parser.py
│   ├── chunker.py
│   ├── indexer.py
│   └── ask.py
├── orchestration/nodes/
│   ├── gap_analyzer.py            # R4: Gap Finder
│   ├── dataset_finder.py          # R5: Dataset Discovery
│   └── citation_graph.py          # R6: Citation Network
├── output/
│   ├── blog_generator.py          # R1: Blog Generator
│   ├── pdf_renderer.py            # R2: LaTeX Preview
│   ├── citation_graph.py          # R6: Graph Export
│   ├── gap_report.py              # R4: Gap Report
│   └── grant_proposal.py          # R7: Grant Proposal
├── tools/
│   ├── huggingface.py             # R5: HuggingFace API
│   └── kaggle.py                  # R5: Kaggle API
├── verification/
│   ├── plagiarism_checker.py      # R8: Plagiarism
│   └── rewrite_suggester.py       # R8: Rewrite Suggest
└── output/templates/grants/       # R7: Grant Templates
    ├── nsf_template.md.j2
    ├── nih_template.md.j2
    └── erc_template.md.j2
```

---

## Implementation Order

```
Phase 1 (Quick Wins — 1-2 days each)
├── R1: Paper-to-Blog Generator
├── R2: Interactive LaTeX Preview
└── R5: Dataset Discovery

Phase 2 (Core Enhancement — 3-4 days each)
├── R3: Research Q&A Chatbot
├── R4: Research Gap Finder
└── R6: Citation Network Visualization

Phase 3 (Advanced — 2-3 days each)
├── R7: Grant Proposal Generator
└── R8: Plagiarism Checker
```

---

*Design approved: May 28, 2026*
*Next step: Implementation via writing-plans skill*
