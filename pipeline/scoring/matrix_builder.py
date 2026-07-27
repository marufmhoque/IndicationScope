"""Builds the mechanism × indication matrix from normalised trial and publication records."""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def build_matrix(
    trials: list[dict],
    publications: list[dict],
) -> list[dict]:
    """
    Return a list of MatrixCell dicts, one per (mechanism_class, indication) pair.

    Args:
        trials: Normalised TrialRecord dicts (with status_class already set).
        publications: Normalised PublicationRecord dicts.

    Returns:
        List of MatrixCell dicts (unsorted; caller applies scoring and ranking).
    """
    # TODO: aggregate trials by (mechanism_class, condition_normalized) key
    # TODO: aggregate publications by the same key
    # TODO: compute trial_count_by_status, publication_count, publication_growth_rate
    # TODO: set has_prior_failure = True if any cell status is COMPLETED_NEGATIVE or TERMINATED
    logger.debug("build_matrix called — trials=%d pubs=%d (stub)", len(trials), len(publications))
    return []
