from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens."""
    return re.findall(r"\w+", text.lower())


def check_similarity(text1: str, text2: str) -> float:
    """Compute Jaccard similarity between two text strings based on token overlap.

    Returns a float in [0.0, 1.0] where 1.0 means identical token sets.
    Uses set-based Jaccard index: |intersection| / |union|.
    """
    tokens1 = set(tokenize(text1))
    tokens2 = set(tokenize(text2))

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2

    return len(intersection) / len(union)


def check_cosine_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity between two texts based on token frequency vectors.

    Returns a float in [0.0, 1.0] where 1.0 means identical frequency distributions.
    Better than Jaccard for capturing partially similar texts.
    """
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    freq1 = Counter(tokens1)
    freq2 = Counter(tokens2)

    all_tokens = set(freq1.keys()) | set(freq2.keys())

    dot_product = 0.0
    norm1 = 0.0
    norm2 = 0.0

    for token in all_tokens:
        f1 = freq1.get(token, 0)
        f2 = freq2.get(token, 0)
        dot_product += f1 * f2
        norm1 += f1 * f1
        norm2 += f2 * f2

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm1) * math.sqrt(norm2))


def check_ngram_overlap(text1: str, text2: str, n: int = 5) -> list[str]:
    """Find overlapping n-grams between two texts.

    Args:
        text1: First text to compare.
        text2: Second text to compare.
        n: Size of n-grams (in words).

    Returns:
        List of overlapping n-gram strings.
    """
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if len(tokens1) < n or len(tokens2) < n:
        return []

    ngrams1 = {" ".join(tokens1[i:i + n]) for i in range(len(tokens1) - n + 1)}
    ngrams2 = {" ".join(tokens2[i:i + n]) for i in range(len(tokens2) - n + 1)}

    return list(ngrams1 & ngrams2)


def flag_flagged_passages(
    passages: list[tuple[str, str, float, str]],
    threshold: float = 0.8,
) -> list[dict[str, Any]]:
    """Filter and format passages that exceed the similarity threshold.

    Args:
        passages: List of (text, source, similarity, match_type) tuples.
        threshold: Similarity threshold above which passages are flagged.

    Returns:
        List of flagged passage dicts with text, source, similarity, and type.
    """
    flagged: list[dict[str, Any]] = []
    for text, source, similarity, match_type in passages:
        if similarity >= threshold:
            flagged.append({
                "text": text[:200],
                "source": source[:200],
                "similarity": round(similarity, 2),
                "type": match_type,
            })
    return flagged


def check_plagiarism(
    generated_text: str,
    source_chunks: list[dict[str, Any]],
    threshold: float = 0.8,
) -> dict[str, Any]:
    """Run a full plagiarism check on generated text against source chunks.

    Uses multiple detection strategies:
    1. Sentence-level Jaccard similarity against each source chunk
    2. Cosine similarity for nuanced paraphrase detection
    3. N-gram overlap for exact copied phrases

    Args:
        generated_text: The text to check (e.g. a generated paper section).
        source_chunks: List of source text chunks, each with a 'text' key.
        threshold: Similarity threshold for flagging (0.0-1.0).

    Returns:
        Dict with overall_score, flagged_sentences, and statistics.
    """
    sentences = re.split(r"(?<=[.!?])\s+", generated_text)
    passages: list[tuple[str, str, float, str]] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:  # Skip very short fragments
            continue

        for chunk in source_chunks:
            source_text = chunk.get("text", "")
            if not source_text:
                continue

            # Method 1: Jaccard similarity
            jaccard_sim = check_similarity(sentence, source_text)

            # Method 2: Cosine similarity (better for paraphrased content)
            cosine_sim = check_cosine_similarity(sentence, source_text)

            # Use the max of both metrics
            best_sim = max(jaccard_sim, cosine_sim)

            if best_sim >= threshold:
                match_type = "paraphrase" if cosine_sim > jaccard_sim else "exact_match"
                passages.append((sentence, source_text[:200], best_sim, match_type))

            # Method 3: N-gram overlap for exact phrase copying
            ngrams = check_ngram_overlap(sentence, source_text, n=6)
            if ngrams and best_sim < 1.0:  # Avoid duplicates already caught by similarity
                passages.append((sentence, source_text[:200], 1.0, "exact_match"))

    flagged = flag_flagged_passages(passages, threshold=threshold)

    total_sentences = max(len(sentences), 1)
    flagged_count = len(flagged)
    exact_matches = sum(1 for f in flagged if f["type"] == "exact_match")
    paraphrases = sum(1 for f in flagged if f["type"] == "paraphrase")

    # Overall score: 1.0 = no issues, 0.0 = completely flagged
    overall_score = round(1.0 - (flagged_count / total_sentences), 2)

    return {
        "overall_score": overall_score,
        "flagged_sentences": flagged,
        "statistics": {
            "total_sentences": total_sentences,
            "flagged": flagged_count,
            "exact_matches": exact_matches,
            "paraphrases": paraphrases,
        },
    }
