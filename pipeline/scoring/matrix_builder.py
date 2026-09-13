"""Builds the mechanism-class matrix from normalised trial and publication records."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from config import EXTRACTION_BUDGET
from pipeline.normalization.entity_extraction import extract_mechanisms_batch
from pipeline.normalization.pillar_mapper import assign_pillar
from pipeline.scoring.literature_index import LiteratureIndex

logger = logging.getLogger(__name__)

UNCLASSIFIED = "Unclassified"

# How the classification budget is split. Trials get the larger share: an
# intervention name is a direct statement of what was tried, whereas a
# publication only implies it.
_TRIAL_SHARE = 0.65

_FAILURE_STATUSES = frozenset(["COMPLETED_NEGATIVE", "TERMINATED"])


def build_matrix(
    trials: list[dict],
    publications: list[dict],
    indication: str,
    max_extraction_items: int | None = None,
) -> dict:
    """
    Aggregate trials and publications into one cell per mechanism class.

    Args:
        trials: Normalised trial dicts, as produced by
            pipeline.normalization.trial_normalizer.normalize_trial.
        publications: Publication dicts, as produced by PubMedClient.
        indication: The disease this search was scoped to. Constant across all
            cells — mechanism_class is the axis that varies within one search.
        max_extraction_items: Cap on records sent to the LLM, from the caller's
            wall-clock guard. 0 skips classification entirely; counts still come
            back with everything under "Unclassified".

    Returns:
        {"cells": [MatrixCell, ...], "coverage": {...}} — coverage reports how
        much of the landscape was actually classified, which at a constrained
        budget is a substantial fraction and must not be presented as complete.
    """
    budget = EXTRACTION_BUDGET if max_extraction_items is None else min(
        EXTRACTION_BUDGET, max_extraction_items
    )

    drug_groups = _group_trials_by_drug(trials)
    items, drugs_selected, _ = _build_extraction_items(drug_groups, publications, budget)
    mechanism_by_source = extract_mechanisms_batch(items)

    cells: dict[str, dict] = {}
    trials_classified = 0
    drugs_classified = 0

    for drug_key, group in drug_groups.items():
        result = mechanism_by_source.get(f"drug:{drug_key}") if drug_key else None
        mech = (result or {}).get("mechanism_class") or UNCLASSIFIED
        drug_class = (result or {}).get("drug_class")
        # The molecular target was extracted alongside the mechanism and used to be
        # discarded; it is the objective source for "affected proteins".
        target = (result or {}).get("target")
        if mech != UNCLASSIFIED:
            drugs_classified += 1
            trials_classified += len(group["trials"])

        for trial in group["trials"]:
            cell = _cell_for(cells, mech, indication)
            if drug_class and not cell["drug_class"]:
                cell["drug_class"] = drug_class
            if target and not cell["target"]:
                cell["target"] = target
            status = trial["status_class"]
            cell["trial_count_by_status"][status] = (
                cell["trial_count_by_status"].get(status, 0) + 1
            )
            for phase in trial.get("phases") or ["UNSPECIFIED"]:
                cell["phase_counts"][phase] = cell["phase_counts"].get(phase, 0) + 1
            if status in _FAILURE_STATUSES:
                cell["has_prior_failure"] = True
            if trial["nct_id"]:
                cell["supporting_nct_ids"].append(trial["nct_id"])

    pubs_classified = 0
    for pub in publications:
        pmid = pub.get("pmid", "")
        result = mechanism_by_source.get(f"pmid:{pmid}")
        mech = (result or {}).get("mechanism_class") or UNCLASSIFIED
        if mech != UNCLASSIFIED:
            pubs_classified += 1

        cell = _cell_for(cells, mech, indication)
        if (result or {}).get("target") and not cell["target"]:
            cell["target"] = result["target"]
        cell["publication_count"] += 1
        if pmid:
            cell["supporting_pmids"].append(pmid)

    # Literature support is counted over every sampled abstract, not just the ~21
    # the model classified, because those yield 0-3 per cell. See literature_index
    # for why the corpus decides which words are distinctive.
    index = LiteratureIndex(publications)

    out = list(cells.values())
    for cell in out:
        cell["literature_support"] = (
            0 if cell["mechanism_class"] == UNCLASSIFIED
            else index.support(cell["mechanism_class"])
        )
        cell["pillar"] = (
            UNCLASSIFIED if cell["mechanism_class"] == UNCLASSIFIED
            else assign_pillar(cell["drug_class"], cell["mechanism_class"])
        )
        cell["supporting_pmids"] = cell["supporting_pmids"][:10]
        cell["supporting_nct_ids"] = cell["supporting_nct_ids"][:10]

    coverage = {
        "distinct_drugs": len(drug_groups),
        "drugs_attempted": drugs_selected,
        "drugs_classified": drugs_classified,
        "trials_total": len(trials),
        "trials_classified": trials_classified,
        "publications_total": len(publications),
        "publications_classified": pubs_classified,
        "abstracts_indexed": len(publications),
        "extraction_budget": budget,
    }

    logger.info(
        "build_matrix: %d cells | trials %d/%d classified | drugs %d classified of "
        "%d attempted (%d distinct) | publications %d/%d | indication=%r",
        len(out), trials_classified, len(trials), drugs_classified, drugs_selected,
        len(drug_groups), pubs_classified, len(publications), indication,
    )
    return {"cells": out, "coverage": coverage}


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _group_trials_by_drug(trials: list[dict]) -> dict[str, dict]:
    """Collapse trials onto the drug they test.

    A single drug recurs across many trials — ranibizumab appears in 13 of 200
    wet-AMD trials — so classifying it once instead of once per trial spends the
    budget on breadth rather than repetition. Trials with no named intervention
    group under "" and stay unclassified; there is nothing to classify.
    """
    groups: dict[str, dict] = defaultdict(
        lambda: {"label": "", "trials": [], "context": ""}
    )
    for trial in trials:
        names = trial.get("intervention_names") or []
        raw = names[0].strip() if names else ""
        key = _canonical_key(raw) if raw else ""
        group = groups[key]
        group["trials"].append(trial)
        if raw and not group["label"]:
            group["label"] = raw
            # Investigational agents are named by code (EYP-1901, ADVM-022), which
            # carries no mechanistic signal on its own. The trial's own text
            # usually states the mechanism, so it travels with the name.
            group["context"] = f"{trial.get('brief_title', '')} {trial.get('brief_summary', '')}"
    return dict(groups)


def _build_extraction_items(
    drug_groups: dict[str, dict], publications: list[dict], budget: int
) -> tuple[list[dict], int, int]:
    """Select what to spend the classification budget on.

    Drugs are taken most-frequent-first so each call covers as many trials as
    possible. Returns (items, drugs_selected, publications_selected).
    """
    if budget <= 0:
        return [], 0, 0

    trial_budget = max(1, int(budget * _TRIAL_SHARE))

    ranked = sorted(
        ((key, g) for key, g in drug_groups.items() if key and g["label"]),
        key=lambda kv: len(kv[1]["trials"]),
        reverse=True,
    )
    items = [
        {
            "source_id": f"drug:{key}",
            "text": f"{group['label']}. Trial context: {group['context']}".strip(),
        }
        for key, group in ranked[:trial_budget]
    ]
    drugs_selected = len(items)

    # Whatever the drugs didn't use goes to publications rather than being lost.
    pub_budget = budget - drugs_selected
    pub_candidates = [p for p in publications if p.get("pmid")]
    for pub in pub_candidates[:pub_budget]:
        text = f"{pub.get('title', '')}. {pub.get('abstract', '')}"[:800]
        items.append({"source_id": f"pmid:{pub['pmid']}", "text": text})

    return items, drugs_selected, len(items) - drugs_selected


def _cell_for(cells: dict[str, dict], mechanism_class: str, indication: str) -> dict:
    """Group by a canonicalized key so e.g. "orexin-2 receptor agonist" and
    "orexin 2 receptor agonist" land in the same cell — independent per-item
    extraction calls otherwise phrase the same mechanism differently often
    enough to fragment identical results. The first-seen phrasing is kept."""
    key = _canonical_key(mechanism_class)
    if key not in cells:
        cells[key] = {
            "mechanism_class": mechanism_class,
            "indication": indication,
            "trial_count_by_status": {},
            "phase_counts": {},
            "drug_class": None,
            "target": None,
            "pillar": None,
            "publication_count": 0,
            "literature_support": 0,
            "has_prior_failure": False,
            "rationale": None,
            "supporting_pmids": [],
            "supporting_nct_ids": [],
        }
    return cells[key]


def _canonical_key(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[-_]", " ", lowered)
    lowered = re.sub(r"\breceptor\b", "", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
