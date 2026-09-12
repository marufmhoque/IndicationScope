"""White-space scoring.

White space is a mechanism with literature behind it that the clinic has not
crowded into. Both halves are required: literature alone is a research topic,
and an empty trial landscape alone is an absence of evidence, not an opportunity.

    score = evidence * (0.70 + 0.30 * openness) - 0.40 * failure_penalty

The previous formula carried two terms that could not vary — `population_fit`
was hardcoded to 0.5 (a flat +0.10 on every cell) and `publication_growth_rate`
was structurally 1.0, since esearch returns the most recent papers so every
sampled abstract sat inside the "recent" window. Together they were 45% of the
weight and resolved to a constant plus a yes/no, which is why scores arrived in
two buckets: measured live, progeria returned nine candidates tied at exactly 37
and five wet-AMD candidates tied at exactly 10.
"""

from __future__ import annotations

import math

from pipeline.scoring.matrix_builder import UNCLASSIFIED

# How much of the score openness can modulate. Evidence is the base because a
# mechanism nobody has written about is not an opportunity regardless of how
# empty its trial landscape is.
_EVIDENCE_BASE = 0.70
_OPENNESS_BONUS = 0.30

_FAILURE_PENALTY = 0.40


def score_cell(cell: dict, max_support: int) -> float:
    """Compute a white_space_score in [0, 1] and attach its breakdown.

    `max_support` is the strongest literature support in the same scan.
    Normalising against it rather than a fixed saturation point is what keeps
    this working across diseases: sampled corpora range from ~2,800
    publications (progeria) to ~284,000 (type 2 diabetes), and no absolute
    constant is meaningful across that span. The cost is that scores compare
    within a scan, not between diseases — which the UI states.
    """
    support = cell.get("literature_support", 0)
    # Log-scaled: support is heavy-tailed. A dominant incumbent draws tens of
    # matches while a genuinely interesting under-explored mechanism draws
    # single digits (measured for wet AMD: 1, 2, 3, 9, 15, 75). Linear
    # normalisation against the incumbent crushes everything below it into
    # noise, which is the opposite of what this view is for.
    evidence = (
        math.log1p(support) / math.log1p(max_support) if max_support > 0 else 0.0
    )

    trial_counts = cell.get("trial_count_by_status", {})
    total_trials = sum(trial_counts.values())
    active_trials = trial_counts.get("ACTIVE", 0)
    openness = 1.0 - (active_trials / total_trials if total_trials else 0.0)

    failure = 1.0 if cell.get("has_prior_failure") else 0.0

    score = evidence * (_EVIDENCE_BASE + _OPENNESS_BONUS * openness)
    score -= _FAILURE_PENALTY * failure
    score = max(0.0, min(1.0, score))

    # Surfaced so the UI can show why a mechanism scored what it did rather than
    # presenting a bare number.
    cell["score_components"] = {
        "literature_support": support,
        "max_support": max_support,
        "evidence": round(evidence, 4),
        "openness": round(openness, 4),
        "active_trials": active_trials,
        "total_trials": total_trials,
        "failure_penalty": failure,
    }
    return score


def rank_cells(cells: list[dict]) -> tuple[list[dict], list[dict], dict | None]:
    """
    Score every cell, then split into (candidates, previously_attempted, unclassified).

    Cells with has_prior_failure=True go to previously_attempted; both lists are
    sorted by white_space_score descending.

    The "Unclassified" bucket is pulled out of both. It holds everything the
    classification budget didn't reach, so it accumulates the most records and
    would otherwise rank first — presenting "we didn't look at these" as the
    strongest opportunity. It is returned separately rather than dropped: when
    no API key is configured every record lands there, and silently discarding
    it would render an empty page with no explanation.
    """
    classified = [c for c in cells if c.get("mechanism_class") != UNCLASSIFIED]
    unclassified = next(
        (c for c in cells if c.get("mechanism_class") == UNCLASSIFIED), None
    )

    # The unclassified bucket is excluded from the normaliser as well as the
    # ranking; it is an artefact of the budget, not a mechanism.
    max_support = max((c.get("literature_support", 0) for c in classified), default=0)

    for cell in cells:
        cell["white_space_score"] = score_cell(cell, max_support)

    candidates = [c for c in classified if not c.get("has_prior_failure")]
    previously_attempted = [c for c in classified if c.get("has_prior_failure")]

    candidates.sort(key=lambda c: c["white_space_score"], reverse=True)
    previously_attempted.sort(key=lambda c: c["white_space_score"], reverse=True)

    return candidates, previously_attempted, unclassified


def rank_by_activity(cells: list[dict]) -> list[dict]:
    """Rank mechanisms by how heavily they are being tested — the inverse view.

    White space asks what is unexplored; this asks what the field has converged
    on, which is the baseline a reader needs before any gap means anything.

    Ordering is by active trials, then late-phase presence, then total trials.
    Phase 4 is post-marketing and therefore strong evidence a drug is approved,
    but ClinicalTrials.gov carries no approval status, so it is surfaced as
    "post-marketing" and never asserted as "approved".
    """
    ranked = [c for c in cells if c.get("mechanism_class") != UNCLASSIFIED]

    def key(cell: dict):
        counts = cell.get("trial_count_by_status", {})
        phases = cell.get("phase_counts", {})
        late = phases.get("PHASE3", 0) + phases.get("PHASE4", 0)
        return (counts.get("ACTIVE", 0), late, sum(counts.values()))

    ranked.sort(key=key, reverse=True)
    return [c for c in ranked if sum(c.get("trial_count_by_status", {}).values()) > 0]
