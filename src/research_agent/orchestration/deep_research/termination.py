from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum score improvement to justify another round
_MIN_IMPROVEMENT_THRESHOLD = 0.05

# After this many rounds with no meaningful improvement, terminate
_MAX_STALLED_ROUNDS = 2

# Minimum coverage score below which we always continue
_MIN_COVERAGE_FOR_TERMINATION = 0.3


@dataclass
class TerminationDecision:
    """Result of a termination check."""

    should_terminate: bool = False
    reason: str = ""
    round_scores: list[float] = field(default_factory=list)
    improvements: list[float] = field(default_factory=list)
    novelty_decay: float = 0.0
    new_items_this_round: int = 0
    total_items: int = 0


def check_termination(
    current_overall: float,
    current_coverage: float,
    current_total_items: int,
    previous_scores: list[float],
    *,
    round_index: int,
    max_rounds: int = 3,
    min_improvement: float = _MIN_IMPROVEMENT_THRESHOLD,
    max_stalled: int = _MAX_STALLED_ROUNDS,
    min_coverage: float = _MIN_COVERAGE_FOR_TERMINATION,
) -> TerminationDecision:
    """Detect diminishing returns across sequential search rounds.

    Uses three heuristics to decide whether to continue searching:

    1. **Novelty decay**: Track the ratio of new items to total items.
       When most items are already seen, further searches add little value.
    2. **Score plateau**: When the weighted evidence score stops improving
       meaningfully across rounds, terminate.
    3. **Absolute minimum**: If coverage is below ``min_coverage``, always
       continue regardless of plateau detection.

    Args:
        current_overall: Overall score from the latest search round
        current_coverage: Coverage score from the latest round
        current_total_items: Total collected items from latest round
        previous_scores: List of overall scores from previous rounds
        round_index: Current round number (0-indexed)
        max_rounds: Maximum search rounds allowed (hard cap)
        min_improvement: Minimum score improvement to justify another round
        max_stalled: Max consecutive rounds below improvement threshold
        min_coverage: Minimum coverage to allow termination

    Returns:
        TerminationDecision with termination flag and reasoning
    """
    # Build score history
    all_scores = list(previous_scores)
    all_scores.append(current_overall)

    improvements: list[float] = []
    for i in range(1, len(all_scores)):
        improvements.append(all_scores[i] - all_scores[i - 1])

    decision = TerminationDecision(
        round_scores=all_scores,
        improvements=improvements,
    )

    # Hard cap: max rounds reached
    if round_index >= max_rounds:
        decision.should_terminate = True
        decision.reason = f"max_rounds_reached ({round_index}/{max_rounds})"
        return decision

    # Absolute minimum coverage check
    if current_coverage < min_coverage:
        decision.should_terminate = False
        decision.reason = (
            f"coverage_below_minimum ({current_coverage:.2f} < {min_coverage})"
        )
        return decision

    # Score plateau detection
    if len(improvements) >= max_stalled:
        recent = improvements[-max_stalled:]
        if all(imp < min_improvement for imp in recent):
            decision.should_terminate = True
            decision.reason = (
                f"score_plateau: last {max_stalled} round(s) below "
                f"{min_improvement:.0%} improvement threshold"
            )
            return decision

    # Novelty decay
    prev_total = previous_scores[-1] if previous_scores else 0  # placeholder
    if previous_scores:
        new_items = max(0, current_total_items - int(prev_total * 10))
    else:
        new_items = current_total_items

    decision.new_items_this_round = new_items
    decision.total_items = current_total_items

    if current_total_items > 0:
        novelty_ratio = new_items / current_total_items
        decision.novelty_decay = 1.0 - novelty_ratio

        if novelty_ratio < 0.1 and round_index >= 1:
            decision.should_terminate = True
            decision.reason = (
                f"novelty_decay: only {new_items}/{current_total_items} new items "
                f"({novelty_ratio:.0%} novelty ratio)"
            )
            return decision

    # Default: continue searching
    decision.reason = "continuing (no termination signal detected)"
    return decision
