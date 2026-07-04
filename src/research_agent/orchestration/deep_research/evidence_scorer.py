from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Weights for each evidence quality factor
_AUTHORITY_WEIGHTS: dict[str, float] = {
    "arxiv": 0.7,
    "semantic_scholar": 0.8,
    "openalex": 0.8,
    "pubmed": 0.9,
    "duckduckgo": 0.3,
    "web_search": 0.3,
    "browser_use": 0.4,
    "web_scrape": 0.3,
    "citation": 0.75,
    "reference": 0.75,
}

# Venue authority mapping
_VENUE_AUTHORITY: dict[str, float] = {
    "nature": 1.0,
    "science": 1.0,
    "cell": 1.0,
    "ieee": 0.9,
    "acm": 0.9,
    "neurips": 0.95,
    "icml": 0.95,
    "cvpr": 0.9,
    "acl": 0.9,
    "arxiv": 0.5,
}

# Citation count thresholds (normalized)
_HIGH_CITATIONS = 100
_MEDIUM_CITATIONS = 20


@dataclass
class EvidenceScore:
    """Structured evidence quality score for a single task/section."""

    overall: float = 0.0
    coverage: float = 0.0
    source_authority: float = 0.0
    recency: float = 0.0
    contradiction_penalty: float = 0.0
    citation_impact: float = 0.0
    num_sources: int = 0
    num_providers: int = 0
    details: dict[str, Any] = field(default_factory=dict)


def score_evidence(
    task_findings: dict[str, Any],
    *,
    contradiction_count: int = 0,
    current_year: int = 2026,
) -> EvidenceScore:
    """Compute a weighted, multi-factor evidence quality score.

    Factors considered:
    - **Coverage**: ratio of items found vs. expected (target = 8 items)
    - **Source authority**: average authority weight across all providers
    - **Recency**: weighted by publication year (5-year half-life)
    - **Citation impact**: average citation count of papers found
    - **Contradiction penalty**: reduced score when contradictions detected
    - **Provider diversity**: bonus for having results from multiple providers

    Returns an ``EvidenceScore`` with the overall score (0.0 - 1.0) and
    individual factor breakdowns.
    """
    if not task_findings:
        return EvidenceScore(overall=0.0, details={"reason": "no_findings"})

    # --- Collect raw metrics ---
    total_items = 0
    provider_authorities: list[float] = []
    provider_names: set[str] = set()
    item_years: list[int] = []
    item_citation_counts: list[int] = []
    warning_count = 0
    metadata_only_count = 0

    for provider, provider_data in task_findings.items():
        if not isinstance(provider_data, dict):
            continue
        provider_names.add(str(provider))

        items = provider_data.get("items", [])
        if not isinstance(items, list):
            continue
        total_items += len(items)

        authority = _AUTHORITY_WEIGHTS.get(str(provider), 0.5)
        provider_authorities.append(authority)

        for item in items:
            if not isinstance(item, dict):
                continue
            # Track year
            year = item.get("year")
            if isinstance(year, (int, float)) and year > 1900:
                item_years.append(int(year))
            # Track citation count
            cc = item.get("citation_count")
            if isinstance(cc, (int, float)):
                item_citation_counts.append(int(cc))
            # Track metadata-only items (snippet/content empty)
            snippet = str(item.get("snippet") or item.get("content") or "").strip()
            if not snippet and item.get("title"):
                metadata_only_count += 1

        warning_count += len(provider_data.get("warnings", [])) if isinstance(provider_data.get("warnings"), list) else 0

    # --- Factor 1: Coverage (0.0 - 1.0) ---
    # Sigmoid curve centered at 8 items, steepness 0.3
    expected_items = 8.0
    coverage = 1.0 / (1.0 + math.exp(-0.3 * (total_items - expected_items)))
    # Metadata penalty: reduce coverage if many items lack content
    if total_items > 0:
        metadata_ratio = metadata_only_count / total_items
        coverage *= max(0.0, 1.0 - metadata_ratio * 0.5)

    # --- Factor 2: Source authority (0.0 - 1.0) ---
    source_authority = sum(provider_authorities) / max(len(provider_authorities), 1) if provider_authorities else 0.0
    # Venue bonus: check item venues
    venue_authority = 0.0
    venue_count = 0
    for provider_data in task_findings.values():
        if not isinstance(provider_data, dict):
            continue
        for item in provider_data.get("items", []):
            if not isinstance(item, dict):
                continue
            journal = str(item.get("journal", "") or "").lower()
            booktitle = str(item.get("booktitle", "") or "").lower()
            for venue_key, auth_score in _VENUE_AUTHORITY.items():
                if venue_key in journal or venue_key in booktitle:
                    venue_authority += auth_score
                    venue_count += 1
                    break
    venue_bonus = (venue_authority / max(venue_count, 1)) * 0.15 if venue_count > 0 else 0.0
    source_authority = min(1.0, source_authority + venue_bonus)

    # --- Factor 3: Recency (0.0 - 1.0) ---
    if item_years:
        # Exponential decay: 5-year half-life
        age_weights = [math.exp(-(current_year - y) / 5.0) for y in item_years]
        recency = sum(age_weights) / len(age_weights)
    else:
        recency = 0.3  # Penalty for no date info

    # --- Factor 4: Citation impact (0.0 - 1.0) ---
    if item_citation_counts:
        # Log-scale: log(1 + c) / log(1 + HIGH_CITATIONS)
        impact_scores = [
            math.log(1 + c) / math.log(1 + _HIGH_CITATIONS)
            for c in item_citation_counts
        ]
        citation_impact = sum(impact_scores) / len(impact_scores)
    else:
        citation_impact = 0.0

    # --- Factor 5: Contradiction penalty ---
    contradiction_penalty = min(0.25, contradiction_count * 0.05)

    # --- Weighted combination ---
    # Weights sum to 1.0
    weights = {
        "coverage": 0.35,
        "source_authority": 0.25,
        "recency": 0.15,
        "citation_impact": 0.15,
        "provider_diversity": 0.10,
    }

    # Provider diversity bonus
    provider_diversity = min(1.0, len(provider_names) / 4.0)

    raw_score = (
        weights["coverage"] * coverage
        + weights["source_authority"] * source_authority
        + weights["recency"] * recency
        + weights["citation_impact"] * citation_impact
        + weights["provider_diversity"] * provider_diversity
    )

    # Apply contradiction penalty
    overall = max(0.0, raw_score - contradiction_penalty)

    # Warning penalty: small reduction for each warning
    if warning_count > 0:
        overall = max(0.0, overall - warning_count * 0.02)

    return EvidenceScore(
        overall=round(overall, 3),
        coverage=round(coverage, 3),
        source_authority=round(source_authority, 3),
        recency=round(recency, 3),
        contradiction_penalty=round(contradiction_penalty, 3),
        citation_impact=round(citation_impact, 3),
        num_sources=total_items,
        num_providers=len(provider_names),
        details={
            "total_items": total_items,
            "providers": sorted(provider_names),
            "metadata_only": metadata_only_count,
            "warnings": warning_count,
            "venue_bonus_applied": venue_count > 0,
        },
    )
