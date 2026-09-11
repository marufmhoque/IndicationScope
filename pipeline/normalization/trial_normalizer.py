"""Flattens raw ClinicalTrials.gov v2 study records into a normalised shape."""

from __future__ import annotations

from pipeline.scoring.status_classifier import classify_status


def normalize_trial(study: dict) -> dict:
    """
    Flatten a raw CT.gov v2 study object (fields nested under protocolSection)
    into: nct_id, brief_title, brief_summary, intervention_names, conditions,
    status_class, lead_sponsor, why_stopped.
    """
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    conditions = protocol.get("conditionsModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    description = protocol.get("descriptionModule", {})
    sponsors = protocol.get("sponsorCollaboratorsModule", {})

    intervention_names = [
        i.get("name", "") for i in arms.get("interventions", []) if i.get("name")
    ]

    # Retained, not just classified: the failure analysis quotes this text, and
    # it is the only record of why a trial actually stopped.
    why_stopped = status.get("whyStopped") or ""

    status_class = classify_status(
        overall_status=status.get("overallStatus", ""),
        why_stopped=why_stopped,
        has_results=bool(study.get("hasResults", False)),
    )

    return {
        "nct_id": ident.get("nctId", ""),
        "brief_title": ident.get("briefTitle", ""),
        "brief_summary": description.get("briefSummary", ""),
        "intervention_names": intervention_names,
        "conditions": conditions.get("conditions", []),
        "status_class": status_class,
        "why_stopped": why_stopped,
        "lead_sponsor": sponsors.get("leadSponsor", {}).get("name", ""),
    }
