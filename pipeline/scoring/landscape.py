"""Organises matrix cells for presentation without judging them.

Mechanisms are split by what the trial record shows — a recorded termination or
negative result, or not — and ordered by how much clinical activity they carry.
Nothing here produces a score or characterises a mechanism as more or less
worth pursuing; the ordering is a count, stated as one.
"""

from __future__ import annotations

from pipeline.scoring.matrix_builder import UNCLASSIFIED


def split_cells(cells: list[dict]) -> tuple[list[dict], list[dict], dict | None]:
    """Split cells into (mechanisms, previously_attempted, unclassified).

    `previously_attempted` holds classified mechanisms with at least one trial
    recorded as terminated or completed with a negative result; `mechanisms`
    holds the remaining classified mechanisms. Both are ordered by activity.

    The unclassified bucket is returned separately. It is an artefact of the
    classification budget rather than a mechanism, and when no API key is
    configured every record lands there — dropping it would render an empty page
    with no explanation.
    """
    unclassified = next(
        (c for c in cells if c.get("mechanism_class") == UNCLASSIFIED), None
    )
    classified = [c for c in cells if c.get("mechanism_class") != UNCLASSIFIED]

    mechanisms = rank_by_activity([c for c in classified if not c.get("has_prior_failure")])
    previously_attempted = rank_by_activity(
        [c for c in classified if c.get("has_prior_failure")]
    )
    return mechanisms, previously_attempted, unclassified


def rank_by_activity(cells: list[dict]) -> list[dict]:
    """Order by active trials, then Phase 3/4 trials, then all trials, then
    supporting abstracts.

    Mechanisms with literature but no trials sort last rather than being
    removed. Phase 4 indicates post-marketing study; ClinicalTrials.gov carries
    no approval status, so nothing downstream should describe it as approval.
    """

    def key(cell: dict):
        counts = cell.get("trial_count_by_status", {})
        phases = cell.get("phase_counts", {})
        late = phases.get("PHASE3", 0) + phases.get("PHASE4", 0)
        return (
            counts.get("ACTIVE", 0),
            late,
            sum(counts.values()),
            cell.get("literature_support", 0),
        )

    return sorted(cells, key=key, reverse=True)
