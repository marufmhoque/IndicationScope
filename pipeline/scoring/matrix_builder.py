"""Builds the mechanism-class matrix from normalised trial and publication records."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from pipeline.normalization.entity_extraction import extract_mechanisms_batch

logger = logging.getLogger(__name__)

_UNCLASSIFIED = "Unclassified"

# Mechanism classification is LLM-based; a search can involve hundreds of
# records, so only a capped subset is sent to the model per source. Records
# beyond the cap still count toward totals, just filed under "Unclassified".
_MAX_TRIAL_ITEMS = 40
_MAX_PUB_ITEMS = 20

_RECENT_YEARS = 3
_FAILURE_STATUSES = frozenset(["COMPLETED_NEGATIVE", "TERMINATED"])


def build_matrix(trials: list[dict], publications: list[dict], indication: str) -> list[dict]:
    """
    Return a list of MatrixCell dicts, one per mechanism_class, aggregated
    from the given (already disease-filtered) trials and publications.

    Args:
        trials: Normalised trial dicts, as produced by
            pipeline.normalization.trial_normalizer.normalize_trial.
        publications: Publication dicts, as produced by PubMedClient.
        indication: The disease this search was scoped to. Constant across
            all cells — mechanism_class is the axis that varies within a
            single search, not indication.

    Returns:
        List of MatrixCell dicts (unsorted; caller applies scoring/ranking).
    """
    mechanism_by_source = extract_mechanisms_batch(_build_extraction_items(trials, publications))

    cells: dict[str, dict] = {}
    now_year = datetime.now(timezone.utc).year

    for trial in trials:
        result = mechanism_by_source.get(f"nct:{trial['nct_id']}")
        mech = (result or {}).get("mechanism_class") or _UNCLASSIFIED
        cell = _cell_for(cells, mech, indication)

        status = trial["status_class"]
        cell["trial_count_by_status"][status] = cell["trial_count_by_status"].get(status, 0) + 1
        if status in _FAILURE_STATUSES:
            cell["has_prior_failure"] = True
        if trial["nct_id"]:
            cell["supporting_nct_ids"].append(trial["nct_id"])

    for pub in publications:
        pmid = pub.get("pmid", "")
        result = mechanism_by_source.get(f"pmid:{pmid}")
        mech = (result or {}).get("mechanism_class") or _UNCLASSIFIED
        cell = _cell_for(cells, mech, indication)

        cell["publication_count"] += 1
        if pmid:
            cell["supporting_pmids"].append(pmid)
        if _pub_year(pub.get("pub_date", "")) >= now_year - _RECENT_YEARS:
            cell["_recent_pub_count"] += 1

    out = list(cells.values())
    for cell in out:
        total_pubs = cell["publication_count"]
        cell["publication_growth_rate"] = (
            cell.pop("_recent_pub_count") / total_pubs if total_pubs else 0.0
        )
        cell["supporting_pmids"] = cell["supporting_pmids"][:10]
        cell["supporting_nct_ids"] = cell["supporting_nct_ids"][:10]

    logger.info(
        "build_matrix: %d mechanism cells from %d trials, %d publications (indication=%r)",
        len(out), len(trials), len(publications), indication,
    )
    return out


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _cell_for(cells: dict[str, dict], mechanism_class: str, indication: str) -> dict:
    """Group by a canonicalized key so e.g. "orexin-2 receptor agonist" and
    "orexin 2 receptor agonist" land in the same cell — independent
    per-item extraction calls otherwise phrase the same mechanism
    differently often enough to fragment obviously-identical results.
    The first-seen raw phrasing is kept as the display label."""
    key = _canonical_key(mechanism_class)
    if key not in cells:
        cells[key] = {
            "mechanism_class": mechanism_class,
            "indication": indication,
            "trial_count_by_status": {},
            "publication_count": 0,
            "publication_growth_rate": 0.0,
            "white_space_score": 0.0,
            "has_prior_failure": False,
            "rationale": None,
            "supporting_pmids": [],
            "supporting_nct_ids": [],
            "_recent_pub_count": 0,
        }
    return cells[key]


def _canonical_key(mechanism_class: str) -> str:
    text = mechanism_class.lower()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\breceptor\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_extraction_items(trials: list[dict], publications: list[dict]) -> list[dict]:
    """Build {source_id, text} items, source-capped so publications always
    get some representation even when the trial list alone exceeds the cap."""
    items: list[dict] = []

    # Only the first intervention name: the extraction prompt is written for
    # a single item and returns one JSON object. Joining multiple drug names
    # invites the model to return one object per drug instead, breaking parsing.
    trial_candidates = [t for t in trials if t["intervention_names"] and t["nct_id"]]
    for trial in trial_candidates[:_MAX_TRIAL_ITEMS]:
        text = trial["intervention_names"][0]
        items.append({"source_id": f"nct:{trial['nct_id']}", "text": text})

    pub_candidates = [p for p in publications if p.get("pmid")]
    for pub in pub_candidates[:_MAX_PUB_ITEMS]:
        text = f"{pub.get('title', '')}. {pub.get('abstract', '')}"[:800]
        items.append({"source_id": f"pmid:{pub['pmid']}", "text": text})

    return items


def _pub_year(pub_date: str) -> int:
    """Best-effort year extraction from a 'YYYY[-Mon[-DD]]' or free-text pub_date."""
    for token in pub_date.replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return 0
