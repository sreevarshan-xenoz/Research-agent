"""Automated Peer Review with Confidence Scoring (P37).

Provides structured multi-persona peer review with per-section confidence
scoring and meta-review aggregation.
"""

from research_agent.peer_review.models import (
    ReviewCriterion,
    ReviewSection,
    PersonaReview,
    PersonaDefinition,
    MetaReview,
)
from research_agent.peer_review.personas import THEORETICAL_PERSONA, APPLIED_PERSONA, EXPERIMENTAL_PERSONA, ALL_PERSONAS
from research_agent.peer_review.scorer import score_section_confidence, score_paper_sections
from research_agent.peer_review.aggregator import aggregate_reviews

__all__ = [
    # Models
    "ReviewCriterion",
    "ReviewSection",
    "PersonaReview",
    "PersonaDefinition",
    "MetaReview",
    # Personas
    "THEORETICAL_PERSONA",
    "APPLIED_PERSONA",
    "EXPERIMENTAL_PERSONA",
    "ALL_PERSONAS",
    # Scoring
    "score_section_confidence",
    "score_paper_sections",
    # Aggregation
    "aggregate_reviews",
]
