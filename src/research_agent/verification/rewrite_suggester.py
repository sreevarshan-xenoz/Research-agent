from __future__ import annotations

import hashlib
import random
from typing import Any


SYNONYM_MAP: dict[str, list[str]] = {
    "use": ["utilize", "employ", "apply", "leverage"],
    "show": ["demonstrate", "indicate", "reveal", "illustrate"],
    "find": ["discover", "identify", "detect", "observe"],
    "method": ["approach", "technique", "methodology", "procedure"],
    "result": ["outcome", "finding", "conclusion", "output"],
    "important": ["significant", "crucial", "essential", "critical"],
    "large": ["substantial", "considerable", "extensive", "significant"],
    "small": ["minor", "modest", "limited", "minimal"],
    "new": ["novel", "innovative", "recent", "emerging"],
    "old": ["traditional", "conventional", "established", "prior"],
    "good": ["effective", "promising", "strong", "robust"],
    "bad": ["poor", "inferior", "suboptimal", "weak"],
    "many": ["numerous", "various", "multiple", "diverse"],
    "change": ["modify", "alter", "transform", "adapt"],
    "help": ["facilitate", "enable", "support", "assist"],
    "need": ["require", "necessitate", "demand", "call for"],
    "based_on": ["derived from", "founded on", "grounded in", "premised on"],
    "in_order_to": ["to", "so as to", "for the purpose of", "with the aim of"],
    "because_of": ["due to", "owing to", "attributable to", "as a result of"],
    "a_lot_of": ["substantial", "considerable", "extensive", "ample"],
}


def _synonym_rewrite(sentence: str, rng: random.Random) -> str:
    """Replace words in the sentence with synonyms using a seeded RNG.

    The RNG is seeded from the sentence hash so the same sentence always
    gets the same rewrite, making the results deterministic.
    """
    import re

    def _replace_word(match: re.Match) -> str:
        word = match.group(0).lower().strip(".,;:!?")
        if word in SYNONYM_MAP and rng.random() < 0.3:
            synonyms = SYNONYM_MAP[word]
            replacement = rng.choice(synonyms)
            # Preserve capitalization
            if match.group(0)[0].isupper():
                replacement = replacement.capitalize()
            return replacement
        return match.group(0)

    return re.sub(r"\b[a-zA-Z]{3,}\b", _replace_word, sentence)


def _restructure_sentence(sentence: str, rng: random.Random) -> str:
    """Apply simple structural transformations to a sentence.

    Moves adverbial phrases and switches between active/passive voice
    to create a naturally different sentence structure.
    """
    import re

    transforms = [
        # Move introductory clause to end
        lambda s: re.sub(
            r"^(While|Although|Despite|Given|Since|Because)\b(.+?),(.+)$",
            r"\3, \1\2",
            s,
        ),
        # Convert passive to active (simple heuristic)
        lambda s: re.sub(
            r"\bwas\s+(\w+ed)\s+by\b",
            lambda m: f"{m.group(1)} by",
            s,
        ),
        # Add introductory phrase
        lambda s: (
            f"Notably, {s[0].lower()}{s[1:]}"
            if rng.random() < 0.25
            else s
        ),
    ]

    for transform in transforms:
        result = transform(sentence)
        if result != sentence and len(result) > 10:
            sentence = result

    return sentence


def suggest_rewrite(text: str, match_type: str = "paraphrase") -> dict[str, Any]:
    """Generate a rewrite suggestion for a potentially plagiarized passage.

    Uses two strategies:
    1. Synonym substitution with a deterministic seed
    2. Sentence restructuring (phrase movement, voice changes)

    Args:
        text: The text passage to rewrite.
        match_type: Either "exact_match" or "paraphrase".

    Returns:
        Dict with 'original', 'rewritten', 'strategy', and 'match_type'.
    """
    if not text.strip() or len(text.strip()) < 10:
        return {
            "original": text,
            "rewritten": text,
            "strategy": "none",
            "match_type": match_type,
        }

    # Use deterministic seed for reproducible results
    seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    strategy = "synonym_substitution"
    rewritten = text

    steps: list[str] = []

    # Strategy 1: Synonym substitution
    if rng.random() < 0.7 or match_type == "exact_match":
        synonym_result = _synonym_rewrite(rewritten, rng)
        if synonym_result != rewritten:
            steps.append("synonym_substitution")
            rewritten = synonym_result

    # Strategy 2: Sentence restructuring
    if rng.random() < 0.4 or match_type == "exact_match":
        restructured = _restructure_sentence(rewritten, rng)
        if restructured != rewritten:
            steps.append("sentence_restructuring")
            rewritten = restructured

    if steps:
        strategy = " + ".join(steps)
    else:
        # Fallback: just add a citation placeholder
        rewritten = rewritten.rstrip(".!?") + " [cite]."
        strategy = "citation_added"

    return {
        "original": text[:200],
        "rewritten": rewritten[:200],
        "strategy": strategy,
        "match_type": match_type,
    }


def batch_suggest_rewrites(
    flagged_sentences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate rewrite suggestions for a batch of flagged sentences.

    Args:
        flagged_sentences: List of flagged passage dicts from check_plagiarism().

    Returns:
        List of rewrite suggestion dicts with original, rewritten, and strategy.
    """
    suggestions: list[dict[str, Any]] = []
    for sentence in flagged_sentences:
        text = sentence.get("text", "")
        match_type = sentence.get("type", "paraphrase")
        suggestion = suggest_rewrite(text, match_type=match_type)
        suggestion["similarity"] = sentence.get("similarity", 0.0)
        suggestion["source"] = sentence.get("source", "")
        suggestions.append(suggestion)
    return suggestions
