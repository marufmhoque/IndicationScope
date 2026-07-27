"""Trial status classification.

Maps the raw ClinicalTrials.gov overallStatus + whyStopped to the project's
five-class taxonomy so failures are never silently dropped.
"""

from __future__ import annotations

_ACTIVE = frozenset(
    ["RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"]
)
_COMPLETED = frozenset(["COMPLETED"])
_TERMINATED = frozenset(["TERMINATED"])
_WITHDRAWN = frozenset(["WITHDRAWN"])

_NEGATIVE_PHRASES = frozenset(
    [
        "lack of efficacy",
        "insufficient efficacy",
        "futility",
        "failed",
        "no benefit",
        "negative results",
        "primary endpoint not met",
        "did not meet",
    ]
)
_SAFETY_PHRASES = frozenset(
    [
        "safety",
        "adverse event",
        "toxicity",
        "adverse effects",
        "side effect",
    ]
)


def classify_status(
    overall_status: str,
    why_stopped: str | None,
    has_results: bool,
) -> str:
    """
    Returns one of:
      ACTIVE | COMPLETED_POSITIVE | COMPLETED_NEGATIVE | TERMINATED | WITHDRAWN | UNKNOWN
    """
    raw = (overall_status or "").upper().replace(" ", "_")
    why = (why_stopped or "").lower()

    if raw in _ACTIVE:
        return "ACTIVE"

    if raw in _WITHDRAWN:
        return "WITHDRAWN"

    if raw in _TERMINATED:
        # Efficacy/safety failure → classify as negative, not just terminated
        if _matches_any(why, _NEGATIVE_PHRASES | _SAFETY_PHRASES):
            return "COMPLETED_NEGATIVE"
        return "TERMINATED"

    if raw in _COMPLETED:
        if has_results:
            if _matches_any(why, _NEGATIVE_PHRASES):
                return "COMPLETED_NEGATIVE"
            return "COMPLETED_POSITIVE"
        # Completed but no results posted — cannot infer outcome
        return "UNKNOWN"

    return "UNKNOWN"


def _matches_any(text: str, phrases: frozenset[str]) -> bool:
    return any(phrase in text for phrase in phrases)
