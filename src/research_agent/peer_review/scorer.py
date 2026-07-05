"""Per-section confidence scoring for automated peer review.

Analyzes paper sections and assigns confidence scores (0.0-1.0) based on
structural completeness, citation density, methodological clarity, and
cross-referencing quality.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Heuristic scorers for various section quality dimensions
# ---------------------------------------------------------------------------


def _compute_length_score(text: str, min_chars: int = 200, ideal_chars: int = 2000) -> float:
    """Score a section based on its length relative to expectations.

    Returns a score from 0.0 (too short) to 1.0 (adequate length).
    """
    length = len(text.strip())
    if length >= ideal_chars:
        return 1.0
    if length <= min_chars:
        return max(0.0, length / min_chars * 0.5)
    # Linear interpolation between min and ideal
    return 0.5 + 0.5 * (length - min_chars) / (ideal_chars - min_chars)


def _compute_citation_score(text: str) -> float:
    """Score a section based on citation density.

    Expects \\cite{...} references and rewards having citations.
    Too few indicates weak evidence grounding.
    """
    citations = re.findall(r'\\cite\{[^}]*\}', text)
    num_citations = len(citations)
    if num_citations >= 5:
        return 1.0
    if num_citations >= 3:
        return 0.8
    if num_citations >= 1:
        return 0.5
    return 0.1


def _compute_coherence_score(text: str) -> float:
    """Estimate section coherence based on structural signals.

    Looks for transition words, bullet points, sub-sections, and
    connective phrases that suggest well-structured prose.
    """
    coherence_signals = 0
    # Transition words
    transitions = re.findall(
        r'\b(however|therefore|furthermore|moreover|in addition|'
        r'consequently|nevertheless|on the other hand|in contrast|'
        r'firstly|secondly|finally|specifically|in particular)\b',
        text.lower(),
    )
    coherence_signals += min(len(transitions), 10)

    # Sub-section headers (LaTeX \subsection or \paragraph)
    headers = re.findall(r'\\(?:sub)?section\{|\\paragraph\{|\\textbf\{[^}]*\}', text)
    coherence_signals += min(len(headers), 5)

    # Evidence of structured lists
    if re.search(r'\\begin\{itemize\}|\\begin\{enumerate\}|\\begin\{description\}', text):
        coherence_signals += 3

    # Normalize to 0-1
    return min(1.0, coherence_signals / 12.0)


def _compute_discipline_score(text: str) -> float:
    """Score the section based on use of discipline-appropriate terminology.

    Rewards the use of technical/academic language and penalizes
    overly casual phrasing.
    """
    academic_markers = re.findall(
        r'\b(analysis|methodology|framework|approach|evaluation|'
        r'experiment|empirical|theoretical|proposed|contribution|'
        r'baseline|benchmark|state-of-the-art|hypothesis|findings)\b',
        text.lower(),
    )
    tech_density = len(academic_markers) / max(1, len(text.split()))
    # Penalize casual language
    casual_markers = re.findall(
        r'\b(kinda|sorta|pretty good|really nice|awesome|basically|just|actually)\b',
        text.lower(),
    )
    casual_penalty = len(casual_markers) * 0.05

    score = min(1.0, tech_density * 20) - casual_penalty
    return max(0.0, score)


# ---------------------------------------------------------------------------
# Section types and their scoring rubrics
# ---------------------------------------------------------------------------


_SECTION_WEIGHTS: dict[str, dict[str, float]] = {
    "abstract": {
        "length": 0.30,
        "coherence": 0.35,
        "discipline": 0.35,
    },
    "introduction": {
        "length": 0.20,
        "citation": 0.25,
        "coherence": 0.30,
        "discipline": 0.25,
    },
    "related work": {
        "length": 0.20,
        "citation": 0.40,
        "coherence": 0.20,
        "discipline": 0.20,
    },
    "methodology": {
        "length": 0.25,
        "citation": 0.20,
        "coherence": 0.25,
        "discipline": 0.30,
    },
    "experiments": {
        "length": 0.20,
        "citation": 0.30,
        "coherence": 0.25,
        "discipline": 0.25,
    },
    "results": {
        "length": 0.25,
        "citation": 0.25,
        "coherence": 0.20,
        "discipline": 0.30,
    },
    "discussion": {
        "length": 0.20,
        "citation": 0.20,
        "coherence": 0.30,
        "discipline": 0.30,
    },
    "conclusion": {
        "length": 0.30,
        "citation": 0.10,
        "coherence": 0.30,
        "discipline": 0.30,
    },
}

_DEFAULT_WEIGHTS: dict[str, float] = {
    "length": 0.25,
    "citation": 0.25,
    "coherence": 0.25,
    "discipline": 0.25,
}


def _normalize_section_name(name: str) -> str:
    """Normalize a section name for rubric lookup."""
    name = name.lower().strip()
    # Strip LaTeX commands
    name = re.sub(r'\\[a-z]+\{', '', name)
    name = re.sub(r'[{}]', '', name)
    name = name.strip()
    # Map to known section types
    if re.search(r'\babstract\b', name):
        return "abstract"
    if re.search(r'\bintroduction\b', name):
        return "introduction"
    if re.search(r'\brelated\s*(work|literature)\b', name):
        return "related work"
    if re.search(r'\bmethod(s|ology)?\b', name):
        return "methodology"
    if re.search(r'\bexperiment(s|al)?\b', name):
        return "experiments"
    if re.search(r'\bresult(s)?\b', name):
        return "results"
    if re.search(r'\bdiscussion\b', name):
        return "discussion"
    if re.search(r'\bconclusion\b', name):
        return "conclusion"
    return "other"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_section_confidence(section_name: str, section_text: str) -> float:
    """Compute an automated confidence score (0.0-1.0) for a single section.

    Uses heuristic signals (length, citations, coherence, academic language)
    weighted by section type.
    """
    weights = _SECTION_WEIGHTS.get(_normalize_section_name(section_name), _DEFAULT_WEIGHTS)
    length_score = _compute_length_score(section_text)
    citation_score = _compute_citation_score(section_text)
    coherence_score = _compute_coherence_score(section_text)
    discipline_score = _compute_discipline_score(section_text)

    total = 0.0
    if "length" in weights:
        total += weights["length"] * length_score
    if "citation" in weights:
        total += weights["citation"] * citation_score
    if "coherence" in weights:
        total += weights["coherence"] * coherence_score
    if "discipline" in weights:
        total += weights["discipline"] * discipline_score

    return round(min(1.0, max(0.0, total)), 3)


def score_paper_sections(combined_sections: list[dict[str, Any]]) -> dict[str, float]:
    """Score all sections in a paper against the automated rubric.

    Args:
        combined_sections: List of dicts with 'title' and optional
            'content', 'text', or 'latex' keys.

    Returns:
        Dict mapping section names to confidence scores (0.0-1.0).
    """
    scores: dict[str, float] = {}
    for section in combined_sections:
        title = section.get("title", "Untitled Section")
        # Try various content key names
        text = (
            section.get("content")
            or section.get("text")
            or section.get("latex")
            or ""
        )
        if not text and isinstance(section.get("findings"), dict):
            text = str(section["findings"])
        scores[title] = score_section_confidence(title, str(text))
    return scores
