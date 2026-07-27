"""White-space scoring formula (Section 11 of the PRD).

white_space_score =
    0.35 * rationale_strength
  + 0.25 * publication_growth_rate
  + 0.20 * population_fit
  - 0.15 * active_trial_density
  - 0.30 * failure_penalty
"""

from __future__ import annotations


def score_cell(cell: dict) -> float:
    """
    Compute and return a white_space_score in [0, 1] for a MatrixCell dict.

    Args:
        cell: A MatrixCell dict as produced by matrix_builder.build_matrix().

    Returns:
        float — higher = more attractive white space.
    """
    # TODO: compute rationale_strength from publication_count + recency
    # TODO: compute population_fit from disease prevalence (orphan threshold: <200k US)
    # TODO: compute active_trial_density from trial_count_by_status["ACTIVE"]
    # TODO: apply failure_penalty = 1.0 if has_prior_failure else 0.0
    return 0.0


def rank_cells(cells: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split and sort cells into (candidates, previously_attempted).

    Cells with has_prior_failure=True go to previously_attempted.
    Remaining cells are sorted by white_space_score descending.
    """
    # TODO: implement after score_cell is complete
    candidates = [c for c in cells if not c.get("has_prior_failure")]
    previously_attempted = [c for c in cells if c.get("has_prior_failure")]
    return candidates, previously_attempted
