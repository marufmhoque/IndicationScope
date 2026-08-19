"""Flattens raw ClinicalTrials.gov v2 study records into a normalised shape."""

from __future__ import annotations

from pipeline.scoring.status_classifier import classify_status


def normalize_trial(study: dict) -> dict:
    """
    Flatten a raw CT.gov v2 study object (fields nested under protocolSection)
    into: nct_id, brief_title, brief_summary, intervention_names, conditions,
    status_class.
    """
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    conditions = protocol.get("conditionsModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    description = protocol.get("descriptionModule", {})

    intervention_names = [
        i.get("name", "") for i in arms.get("interventions", []) if i.get("name")
    ]

    status_class = classify_status(
        overall_status=status.get("overallStatus", ""),
        why_stopped=status.get("whyStopped"),
        has_results=bool(study.get("hasResults", False)),
    )

    return {
        "nct_id": ident.get("nctId", ""),
        "brief_title": ident.get("briefTitle", ""),
        "brief_summary": description.get("briefSummary", ""),
        "intervention_names": intervention_names,
        "conditions": conditions.get("conditions", []),
        "status_class": status_class,
    }
