"""Meta-review aggregation for multi-persona peer review.

Combines multiple PersonaReview objects into a single MetaReview with
consensus scoring, disagreement detection, and aggregated feedback.
"""

from __future__ import annotations

import logging

from research_agent.peer_review.models import (
    PersonaReview,
    MetaReview,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _compute_variance(scores: list[float]) -> float:
    """Compute the variance of a list of scores."""
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    return sum((s - mean) ** 2 for s in scores) / len(scores)


def _aggregate_strengths(reviews: list[PersonaReview]) -> list[str]:
    """Aggregate and deduplicate strengths across reviews.

    Returns top-ranked strengths (up to 10) sorted by frequency.
    """
    strength_counts: dict[str, int] = {}
    for review in reviews:
        for strength in review.strengths:
            normalized = strength.strip().lower()
            # Fuzzy dedup: skip if very similar to an existing key
            matched = False
            for existing in list(strength_counts.keys()):
                # Simple dedup: share first 40+ characters after normalization
                if normalized[:40] == existing[:40]:
                    strength_counts[existing] += 1
                    matched = True
                    break
            if not matched:
                strength_counts[normalized] = 1

    # Sort by frequency, then by length (longer = more specific)
    sorted_strengths = sorted(
        strength_counts.items(),
        key=lambda x: (-x[1], -len(x[0])),
    )
    return [s[0].capitalize() for s in sorted_strengths[:10]]


def _aggregate_weaknesses(reviews: list[PersonaReview]) -> list[str]:
    """Aggregate and deduplicate weaknesses across reviews."""
    weakness_counts: dict[str, int] = {}
    for review in reviews:
        for weakness in review.weaknesses:
            normalized = weakness.strip().lower()
            matched = False
            for existing in list(weakness_counts.keys()):
                if normalized[:40] == existing[:40]:
                    weakness_counts[existing] += 1
                    matched = True
                    break
            if not matched:
                weakness_counts[normalized] = 1

    sorted_weaknesses = sorted(
        weakness_counts.items(),
        key=lambda x: (-x[1], -len(x[0])),
    )
    return [w[0].capitalize() for w in sorted_weaknesses[:10]]


def _aggregate_questions(reviews: list[PersonaReview]) -> list[str]:
    """Aggregate questions from all reviews."""
    all_questions: list[str] = []
    seen: set[str] = set()
    for review in reviews:
        for question in review.questions:
            normalized = question.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                all_questions.append(question.strip())
    return all_questions[:15]  # Cap at 15 questions


def _detect_disagreements(reviews: list[PersonaReview]) -> list[str]:
    """Detect areas of disagreement between reviewers.

    Returns a list of natural-language descriptions of disagreements.
    """
    disagreements: list[str] = []
    if len(reviews) < 2:
        return disagreements

    # Check for large score gaps
    scores = [(r.persona_label, r.overall_score) for r in reviews]
    max_score = max(s for _, s in scores)
    min_score = min(s for _, s in scores)
    if max_score - min_score > 0.3:
        disagreements.append(
            f"Large scoring discrepancy: scores range from "
            f"{min_score:.2f} to {max_score:.2f}"
        )

    # Check for conflicting recommendations
    recs = {r.persona_label: r.recommendation for r in reviews}
    unique_recs = set(recs.values())
    if len(unique_recs) > 1:
        disagreements.append(
            f"Conflicting recommendations: {', '.join(f'{k}: {v}' for k, v in recs.items())}"
        )

    # Check for contradictory strength/weakness claims
    for review_a in reviews:
        for review_b in reviews:
            if review_a.persona >= review_b.persona:
                continue
            a_strengths_lower = {s.lower()[:50] for s in review_a.strengths}
            b_weaknesses_lower = {w.lower()[:50] for w in review_b.weaknesses}
            overlap = a_strengths_lower & b_weaknesses_lower
            if overlap:
                for item in overlap:
                    disagreements.append(
                        f"Disagreement between {review_a.persona_label} and "
                        f"{review_b.persona_label}: one sees '{item[:60]}...' as a "
                        f"strength while the other flags it as a weakness"
                    )

    return disagreements[:5]  # Cap at 5 disagreements


def _compute_consensus_recommendation(
    reviews: list[PersonaReview],
    avg_score: float,
) -> str:
    """Compute consensus recommendation from individual recommendations."""
    rec_order = ["reject", "major-revision", "minor-revision", "accept"]
    rec_values = [rec_order.index(r.recommendation) for r in reviews]
    avg_rec = sum(rec_values) / len(rec_values) if rec_values else 1

    # Use average recommendation as base, adjust with score
    if avg_score >= 0.8 and avg_rec >= 2.5:
        return "accept"
    if avg_score >= 0.6 and avg_rec >= 1.5:
        return "minor-revision"
    if avg_score >= 0.3:
        return "major-revision"
    return "reject"


# ---------------------------------------------------------------------------
# Main aggregation function
# ---------------------------------------------------------------------------


def aggregate_reviews(reviews: list[PersonaReview]) -> MetaReview:
    """Aggregate multiple persona reviews into a single MetaReview.

    Args:
        reviews: List of PersonaReview objects from different personas.

    Returns:
        A MetaReview containing aggregated scores, feedback, and
        consensus information.
    """
    if not reviews:
        return MetaReview(
            persona_count=0,
            overall_score=0.0,
            overall_confidence=0.0,
        )

    # Compute average scores
    scores = [r.overall_score for r in reviews]
    confidences = [r.overall_confidence for r in reviews]
    avg_score = sum(scores) / len(scores)
    avg_confidence = sum(confidences) / len(confidences)

    # Compute variance
    variance = _compute_variance(scores)

    # Build per-persona score maps
    per_persona_scores = {r.persona_label: r.overall_score for r in reviews}
    per_persona_confidence = {r.persona_label: r.overall_confidence for r in reviews}

    # Aggregate feedback
    aggregated_strengths = _aggregate_strengths(reviews)
    aggregated_weaknesses = _aggregate_weaknesses(reviews)
    consensus_questions = _aggregate_questions(reviews)
    disagreement_areas = _detect_disagreements(reviews)
    consensus_rec = _compute_consensus_recommendation(reviews, avg_score)

    # Generate meta-review text (structured summary)
    meta_text_parts: list[str] = [
        f"# Meta-Review (Aggregated from {len(reviews)} Reviewer Personas)",
        "",
        f"**Overall Score:** {avg_score:.3f} / 1.0",
        f"**Overall Confidence:** {avg_confidence:.3f} / 1.0",
        f"**Score Variance:** {variance:.4f}",
        f"**Consensus Recommendation:** {consensus_rec}",
        "",
    ]

    # Per-persona breakdown
    meta_text_parts.append("## Per-Reviewer Scores")
    meta_text_parts.append("")
    for r in reviews:
        rec_emoji = {"accept": "✅", "minor-revision": "🔄", "major-revision": "⚠️", "reject": "❌"}
        emoji = rec_emoji.get(r.recommendation, "❓")
        meta_text_parts.append(
            f"- **{r.persona_label}**: {r.overall_score:.3f} confidence={r.overall_confidence:.3f} "
            f"{emoji} {r.recommendation}"
        )

    meta_text_parts.append("")

    # Strengths
    if aggregated_strengths:
        meta_text_parts.append("## Key Strengths (Consensus)")
        meta_text_parts.append("")
        for i, s in enumerate(aggregated_strengths, 1):
            meta_text_parts.append(f"{i}. {s}")
        meta_text_parts.append("")

    # Weaknesses
    if aggregated_weaknesses:
        meta_text_parts.append("## Key Weaknesses (Consensus)")
        meta_text_parts.append("")
        for i, w in enumerate(aggregated_weaknesses, 1):
            meta_text_parts.append(f"{i}. {w}")
        meta_text_parts.append("")

    # Open questions
    if consensus_questions:
        meta_text_parts.append("## Questions for Authors")
        meta_text_parts.append("")
        for i, q in enumerate(consensus_questions, 1):
            meta_text_parts.append(f"{i}. {q}")
        meta_text_parts.append("")

    # Disagreements
    if disagreement_areas:
        meta_text_parts.append("## Reviewer Disagreements")
        meta_text_parts.append("")
        for d in disagreement_areas:
            meta_text_parts.append(f"- {d}")
        meta_text_parts.append("")

    return MetaReview(
        persona_count=len(reviews),
        overall_score=round(avg_score, 3),
        overall_confidence=round(avg_confidence, 3),
        aggregated_strengths=aggregated_strengths,
        aggregated_weaknesses=aggregated_weaknesses,
        consensus_questions=consensus_questions,
        score_variance=round(variance, 4),
        per_persona_scores=per_persona_scores,
        per_persona_confidence=per_persona_confidence,
        consensus_recommendation=consensus_rec,
        meta_review_text="\n".join(meta_text_parts),
        disagreement_areas=disagreement_areas,
    )
