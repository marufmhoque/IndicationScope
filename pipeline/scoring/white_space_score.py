"""White-space scoring formula (Section 11 of the PRD).

white_space_score =
    0.35 * rationale_strength
  + 0.25 * publication_growth_rate
  + 0.20 * population_fit
  - 0.15 * active_trial_density
  - 0.30 * failure_penalty
"""

from __future__ import annotations

# Publication count at which rationale_strength saturates to 1.0.
_PUB_COUNT_SATURATION = 20

# No disease-prevalence data source is wired up yet (would need an
# orphan-disease/prevalence dataset), so population_fit is a neutral
# placeholder rather than a real signal until one is added.
_POPULATION_FIT_PLACEHOLDER = 0.5


def score_cell(cell: dict) -> float:
    """
    Compute a white_space_score in [0, 1] for a MatrixCell dict.

    Higher = more attractive white space: growing literature interest,
    without a crowded active-trial landscape or a prior failure signal.
    """
    rationale_strength = min(cell.get("publication_count", 0) / _PUB_COUNT_SATURATION, 1.0)
    publication_growth_rate = cell.get("publication_growth_rate", 0.0)
    population_fit = _POPULATION_FIT_PLACEHOLDER

    trial_counts = cell.get("trial_count_by_status", {})
    total_trials = sum(trial_counts.values())
    active_trials = trial_counts.get("ACTIVE", 0)
    active_trial_density = active_trials / total_trials if total_trials else 0.0

    failure_penalty = 1.0 if cell.get("has_prior_failure") else 0.0

    score = (
        0.35 * rationale_strength
        + 0.25 * publication_growth_rate
        + 0.20 * population_fit
        - 0.15 * active_trial_density
        - 0.30 * failure_penalty
    )
    return max(0.0, min(1.0, score))


def rank_cells(cells: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Score every cell, then split and sort into (candidates, previously_attempted).

    Cells with has_prior_failure=True go to previously_attempted. Both lists
    are sorted by white_space_score descending.
    """
    for cell in cells:
        cell["white_space_score"] = score_cell(cell)

    candidates = [c for c in cells if not c.get("has_prior_failure")]
    previously_attempted = [c for c in cells if c.get("has_prior_failure")]

    candidates.sort(key=lambda c: c["white_space_score"], reverse=True)
    previously_attempted.sort(key=lambda c: c["white_space_score"], reverse=True)

    return candidates, previously_attempted
