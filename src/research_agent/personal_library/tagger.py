"""
P28: Personal Research Library — LLM-based Auto-Tagging

Automatically generates topic tags for library entries using:
- LLM-based topic classification (when available)
- Keyword extraction fallback (always available)
- Venue-based default tags
"""

from __future__ import annotations

import logging
import re

from research_agent.personal_library.models import (
    TagSuggestion,
    LibraryEntry,
    LibraryItem,
    Author,
)

logger = logging.getLogger(__name__)

# Domain-specific keyword maps for keyword-based tagging fallback
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "machine-learning": [
        "neural network", "deep learning", "machine learning", "supervised",
        "unsupervised", "reinforcement learning", "transformer", "attention",
        "backpropagation", "gradient descent", "convolutional", "lstm",
        "generative", "discriminative", "embedding", "representation learning",
    ],
    "nlp": [
        "natural language", "language model", "text generation", "sentiment",
        "named entity", "question answering", "machine translation", "summarization",
        "tokenization", "bert", "gpt", "llm", "prompt", "semantic parsing",
    ],
    "computer-vision": [
        "image recognition", "object detection", "image segmentation", "visual",
        "convolutional neural network", "cnn", "image generation", "video analysis",
        "pose estimation", "facial recognition", "scene understanding",
    ],
    "reinforcement-learning": [
        "reinforcement learning", "rl", "markov decision", "q-learning",
        "policy gradient", "actor-critic", "reward", "exploration", "deep rl",
    ],
    "optimization": [
        "optimization", "convex", "non-convex", "gradient", "stochastic",
        "evolutionary", "genetic algorithm", "particle swarm", "simulated annealing",
    ],
    "data-systems": [
        "database", "data management", "query", "indexing", "storage",
        "distributed system", "data pipeline", "etl", "data warehouse",
        "stream processing", "key-value", "sql", "nosql",
    ],
    "security": [
        "security", "privacy", "encryption", "authentication", "adversarial",
        "differential privacy", "federated learning", "secure computation",
        "malware", "intrusion detection", "cryptography",
    ],
    "theoretical-cs": [
        "complexity", "algorithm", "approximation", "np-complete", "graph theory",
        "combinatorial", "information theory", "computability",
    ],
    "robotics": [
        "robot", "autonomous", "control", "planning", "slam", "manipulation",
        "sensor fusion", "motion planning", "sim-to-real",
    ],
    "healthcare": [
        "medical", "clinical", "healthcare", "diagnosis", "prognosis",
        "biomedical", "genomics", "drug discovery", "patient", "disease",
    ],
}

VENUE_DOMAIN_MAP: dict[str, str] = {
    "neurips": "machine-learning",
    "icml": "machine-learning",
    "iclr": "machine-learning",
    "jmlr": "machine-learning",
    "aaai": "machine-learning",
    "acl": "nlp",
    "emnlp": "nlp",
    "naacl": "nlp",
    "cvpr": "computer-vision",
    "iccv": "computer-vision",
    "eccv": "computer-vision",
    "sigmod": "data-systems",
    "vldb": "data-systems",
    "icde": "data-systems",
    "ieee symposium": "security",
    "ccs": "security",
    "usenix": "security",
}


class AutoTagger:
    """Automatically suggest tags for library entries."""

    def __init__(self, min_confidence: float = 0.15):
        self.min_confidence = min_confidence

    def suggest_tags(self, entry: LibraryEntry) -> list[TagSuggestion]:
        """Generate tag suggestions for a library entry.

        Uses a combination of:
        1. Keyword-based domain matching
        2. Venue-based domain inference
        3. Author/title keyword extraction
        """
        suggestions: list[TagSuggestion] = []
        text_for_analysis = f"{entry.title} {entry.abstract} {' '.join(t.name for t in entry.authors)}"

        # 1. Keyword-based domain matching
        matched_domains = self._match_domains(text_for_analysis.lower())
        for domain, confidence in matched_domains:
            if confidence >= self.min_confidence:
                suggestions.append(TagSuggestion(
                    tag=domain,
                    confidence=confidence,
                    source="auto",
                ))

        # 2. Venue-based domain inference
        if entry.venue:
            venue_lower = entry.venue.lower().strip()
            for venue_key, domain in VENUE_DOMAIN_MAP.items():
                if venue_key in venue_lower:
                    # Don't duplicate if already suggested by keyword matching
                    if not any(s.tag == domain for s in suggestions):
                        suggestions.append(TagSuggestion(
                            tag=domain,
                            confidence=0.5,
                            source="auto",
                        ))

        # 3. Extract key technical terms from title
        key_terms = self._extract_key_terms(entry.title)
        for term, confidence in key_terms:
            # Don't over-tag with too many specific terms
            if len(suggestions) >= 8:
                break
            if not any(s.tag == term for s in suggestions):
                suggestions.append(TagSuggestion(
                    tag=term,
                    confidence=confidence,
                    source="auto",
                ))

        return suggestions

    def _match_domains(self, text: str) -> list[tuple[str, float]]:
        """Match text against domain keyword lists and return confidence scores."""
        results: list[tuple[str, float]] = []

        for domain, keywords in DOMAIN_KEYWORDS.items():
            matches = 0
            for kw in keywords:
                if kw in text:
                    matches += 1

            if matches > 0:
                # Confidence based on proportion of matched keywords relative to total
                # Closer to 1.0 if more keywords match
                ratio = matches / min(len(keywords), 10)
                confidence = min(0.95, 0.2 + ratio * 0.6)
                results.append((domain, round(confidence, 3)))

        # Sort by confidence descending
        results.sort(key=lambda x: -x[1])
        return results[:5]

    def _extract_key_terms(self, title: str) -> list[tuple[str, float]]:
        """Extract important technical terms from a title."""
        # Common stop words in academic titles
        stop_words = {
            "a", "an", "the", "and", "or", "for", "of", "in", "on", "to",
            "with", "via", "using", "based", "towards", "toward", "new",
            "novel", "efficient", "effective", "improved", "learning",
            "method", "approach", "framework", "model", "system", "study",
            "analysis", "results", "performance", "large-scale", "end-to-end",
        }

        # Extract capitalized phrases (proper nouns, acronyms, technical terms)
        words = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", title)
        phrases = re.findall(r"[A-Z]{2,}(?:\s*[A-Z]+)*", title)

        terms: list[tuple[str, float]] = []
        seen = set()

        for phrase in phrases:  # Acronyms first (higher confidence)
            p = phrase.strip().lower()
            if p not in seen and len(p) >= 2 and p not in stop_words:
                seen.add(p)
                terms.append((p, 0.7))

        for phrase in words:  # Capitalized words/phrases
            p = phrase.strip().lower()
            if p not in seen and len(p) >= 4 and p not in stop_words:
                seen.add(p)
                confidence = 0.4 if len(p.split()) > 1 else 0.3
                terms.append((p, confidence))

        return terms[:6]

    def batch_suggest(self, entries: list[LibraryEntry]) -> dict[str, list[TagSuggestion]]:
        """Generate tag suggestions for multiple entries at once."""
        return {entry.entry_id: self.suggest_tags(entry) for entry in entries}


# ── Standalone convenience functions (used by routes.py) ────────────────────


def get_suggested_tags(item: LibraryItem) -> list[str]:
    """Get tag suggestions for a library item without saving."""
    tagger = AutoTagger()
    entry = LibraryEntry(
        entry_id=item.id,
        title=item.title,
        authors=[Author(name=a) for a in item.authors],
        abstract=item.abstract,
        year=item.year or item.published_at,
        venue=item.venue,
        tags=item.tags,
    )
    suggestions = tagger.suggest_tags(entry)
    return [s.tag for s in suggestions]


async def auto_tag_item(item: LibraryItem) -> list[str]:
    """Auto-tag a library item using keyword/LLM analysis.

    Currently uses the AutoTagger keyword engine. In the future this
    can be extended to call an LLM for more sophisticated tagging.
    """
    return get_suggested_tags(item)
