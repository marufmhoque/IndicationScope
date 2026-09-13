import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

# Nothing else loaded .env.local — locally-run uvicorn never saw
# ANTHROPIC_API_KEY/NCBI_API_KEY without this. Must run before the clients
# below read those vars at import/construction time. A no-op in deployed
# environments (Vercel), which inject real env vars instead of this file.
load_dotenv(".env.local")

from config import SYNTHESIS_TOP_N
from fastapi import APIRouter, FastAPI
from mangum import Mangum
from pydantic import BaseModel

from pipeline.ingestion.cache import BriefingCache
from pipeline.ingestion.orchestrator import IngestionOrchestrator
from pipeline.normalization.entity_aggregator import (
    aggregate_organizations,
    aggregate_researchers,
)
from pipeline.normalization.trial_normalizer import normalize_trial
from pipeline.scoring.landscape import split_cells
from pipeline.scoring.matrix_builder import build_matrix
from pipeline.synthesis.rationale_generator import (
    BRIEFING_SECTIONS,
    generate_executive_briefing,
    generate_failure_analysis,
    generate_rationale,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="IndicationScope API")
handler = Mangum(app, lifespan="off")

# Vercel Hobby caps a function at 60s. Stay clear of it: the scan returns
# whatever is ready rather than letting the platform kill the request, since a
# 504 gives the user nothing at all.
_SCAN_BUDGET_S = 45
# Below this much remaining time, skip LLM classification entirely — counts still
# come back, everything just lands in "Unclassified".
_MIN_EXTRACTION_S = 12
# Measured extraction throughput (16 workers, ~0.85s per call). Only used to
# size the item cap against the remaining budget.
_ITEMS_PER_SECOND = 14

# Trial statuses reported in the brief's historical-failures section, with the
# registry's stated reason quoted alongside.
_STOPPED_STATUSES = frozenset(["TERMINATED", "COMPLETED_NEGATIVE", "WITHDRAWN"])
_STOPPED_TRIALS_IN_CONTEXT = 15

_FACET_LABELS = {
    "overview": "DISEASE OVERVIEW AND PATHOPHYSIOLOGY",
    "epidemiology": "EPIDEMIOLOGY",
    "cost": "COST OF ILLNESS AND TREATMENT COST",
}

# Constructed on first use, not at import. Module-scope construction meant any
# init failure (e.g. a read-only filesystem) became a boot-time 500 on every route.
_ingestion: IngestionOrchestrator | None = None
_briefing_cache: BriefingCache | None = None


def get_ingestion() -> IngestionOrchestrator:
    global _ingestion
    if _ingestion is None:
        _ingestion = IngestionOrchestrator()
    return _ingestion


def get_briefing_cache() -> BriefingCache:
    global _briefing_cache
    if _briefing_cache is None:
        _briefing_cache = BriefingCache()
    return _briefing_cache


class ScanRequest(BaseModel):
    disease: str
    mechanism: str | None = None


class SynthesisRequest(BaseModel):
    """Stateless: the client passes back the context /api/scan gave it.

    Re-deriving context server-side would mean re-running ingestion, and the
    serverless cache is per-instance — a cold instance would refetch everything.
    """

    mechanism_class: str
    indication: str
    supporting_pmids: list[str] = []
    supporting_nct_ids: list[str] = []
    abstracts: list[str] = []
    trial_summaries: list[str] = []


class BriefingRequest(BaseModel):
    """Stateless like the other synthesis endpoints: /api/scan hands the client
    the aggregated evidence and it comes back here."""

    indication: str
    context: str
    coverage_note: str = ""


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/scan")
def scan(body: ScanRequest):
    started = time.monotonic()

    ingested = get_ingestion().fetch_all_sources(body.disease, body.mechanism)
    sources = ingested["sources"]
    ct = sources["clinical_trials"]
    pubmed = sources["pubmed"]
    publications = pubmed["records"]
    patents = sources["google_patents"]["records"] + sources["uspto"]["records"]

    trials = [normalize_trial(t) for t in ct["records"]]

    matrix = build_matrix(
        trials,
        publications,
        indication=body.disease,
        max_extraction_items=_extraction_budget(started),
    )
    mechanisms, previously_attempted, unclassified = split_cells(matrix["cells"])
    organizations = aggregate_organizations(trials, patents, limit=30)
    phases = _phase_distribution(trials)
    trend = ingested.get("publication_trend", {"years": {}, "partial_year": 0})
    trial_sampling = _fraction(len(trials), ct["total"])
    publication_sampling = _fraction(len(publications), pubmed["total"])

    # Both lists can request synthesis, so their leading entries carry source text.
    _attach_context(mechanisms[:SYNTHESIS_TOP_N], trials, publications)
    _attach_context(previously_attempted[:SYNTHESIS_TOP_N], trials, publications)

    logger.info(
        "Scan complete — disease=%r mechanisms=%d prior=%d elapsed=%.1fs",
        body.disease, len(mechanisms), len(previously_attempted),
        time.monotonic() - started,
    )

    return {
        "query": {"disease": body.disease, "mechanism": body.mechanism},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mechanisms": mechanisms,
        "previously_attempted": previously_attempted,
        # What the classification budget didn't reach, reported as counts rather
        # than presented as a mechanism.
        "unclassified": _unclassified_summary(unclassified),
        "coverage": matrix["coverage"],
        "phase_distribution": phases,
        "publication_trend": trend,
        # How much of each corpus the scan examined. Ranges from ~2% of registered
        # trials (type 2 diabetes) to 100% (rare indications); the UI and the
        # brief both calibrate to it.
        "sampling": {"trials": trial_sampling, "publications": publication_sampling},
        "briefing_context": _briefing_context(
            mechanisms, previously_attempted, trials, publications, phases, trend,
            organizations,
        ),
        "coverage_note": _coverage_note(trial_sampling, publication_sampling),
        # Ranked across both kinds so academic sponsors survive an industry-heavy
        # field; the UI caps each kind separately.
        "key_organizations": organizations,
        "key_researchers": aggregate_researchers(publications),
        # *_count is the true number of matches; *_analyzed is what was ingested.
        "trial_count": ct["total"],
        "trials_analyzed": len(trials),
        "publication_count": pubmed["total"],
        "publications_analyzed": len(publications),
        "patent_count": sources["uspto"]["total"] + sources["google_patents"]["total"],
        "patents_analyzed": len(patents),
    }


@router.post("/rationale")
def rationale(body: SynthesisRequest):
    """Summarise the evidence for one mechanism.

    Split out of /scan because synthesis is the most expensive step and would
    otherwise push a scan past the platform's function timeout.
    """
    return generate_rationale(_cell_from(body), body.abstracts, body.trial_summaries)


@router.post("/failure-analysis")
def failure_analysis(body: SynthesisRequest):
    """Summarise why prior trials of one mechanism stopped.

    Runs on demand rather than during the scan: most rows are never expanded.
    """
    return generate_failure_analysis(_cell_from(body), body.abstracts, body.trial_summaries)


@router.post("/briefing")
def briefing(body: BriefingRequest):
    """Write the disease intelligence brief.

    Runs on demand rather than inside /api/scan: it is the largest model call in
    the app and also performs its own background literature retrieval, so it
    spends this request's time budget rather than the scan's.
    """
    cache = get_briefing_cache()
    cached = cache.get(body.indication)
    if cached:
        logger.info("Brief cache hit for %r", body.indication)
        return cached

    background = get_ingestion().pubmed.fetch_background(body.indication)
    sections = generate_executive_briefing(
        body.indication,
        body.context,
        body.coverage_note,
        _background_context(background),
    )
    result = {**sections, "references": _background_references(background)}

    # Only cache a brief that actually said something; caching an all-null result
    # would make a transient failure permanent.
    if any(sections.get(key) for key in BRIEFING_SECTIONS):
        cache.set(body.indication, result)
    return result


# Vercel rewrites preserve the original request path, so in production the
# function sees the basePath-prefixed URL. Mounting both keeps local dev (where
# Next strips the prefix before proxying) working against the same code.
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/tools/indicationscope/api")


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _cell_from(body: SynthesisRequest) -> dict:
    return {
        "mechanism_class": body.mechanism_class,
        "indication": body.indication,
        "supporting_pmids": body.supporting_pmids,
        "supporting_nct_ids": body.supporting_nct_ids,
    }


def _extraction_budget(started: float) -> int:
    """How many records classification can afford with the time left."""
    remaining = _SCAN_BUDGET_S - (time.monotonic() - started)
    if remaining < _MIN_EXTRACTION_S:
        logger.warning(
            "Only %.1fs of budget left after ingestion — skipping mechanism classification",
            remaining,
        )
        return 0
    return max(0, int((remaining - 5) * _ITEMS_PER_SECOND))


def _fraction(part: int, whole: int) -> dict:
    return {
        "ingested": part,
        "total": whole,
        "fraction": (part / whole) if whole else 0.0,
    }


def _phase_distribution(trials: list[dict]) -> dict:
    """Phase counts plus the trial totals they were drawn from.

    A trial registered as PHASE1|PHASE2 contributes to both buckets, so counts sum
    to more than the number of trials; the totals travel alongside. Trials with no
    phase get their own bucket rather than being dropped.
    """
    counts: dict[str, int] = {}
    phased = 0
    for trial in trials:
        trial_phases = trial.get("phases") or []
        if trial_phases:
            phased += 1
        for phase in trial_phases or ["UNSPECIFIED"]:
            counts[phase] = counts.get(phase, 0) + 1
    return {"counts": counts, "phased_trials": phased, "total_trials": len(trials)}


def _coverage_note(trials: dict, publications: dict) -> str:
    """One sentence telling the model how much of the record it is seeing."""
    return (
        f"This analysis examined {trials['ingested']} of {trials['total']} registered "
        f"trials ({_percent(trials['fraction'])}) and {publications['ingested']} of "
        f"{publications['total']} publications ({_percent(publications['fraction'])}). "
        "Calibrate every claim to that coverage."
    )


def _percent(fraction: float) -> str:
    """A small nonzero share must not round to "0%", which reads as nothing examined."""
    if fraction >= 0.995:
        return "100%"
    if 0 < fraction < 0.01:
        return "under 1%"
    return f"{fraction:.0%}"


def _mechanism_lines(cells: list[dict], limit: int) -> list[str]:
    lines = []
    for cell in cells[:limit]:
        counts = cell.get("trial_count_by_status", {})
        phase_mix = ", ".join(
            f"{k}:{v}" for k, v in sorted(cell.get("phase_counts", {}).items())
        )
        descriptors = [
            f"target: {cell['target']}" if cell.get("target") else None,
            f"class: {cell['drug_class']}" if cell.get("drug_class") else None,
            f"modality: {cell['pillar']}" if cell.get("pillar") else None,
        ]
        described = "; ".join(d for d in descriptors if d)
        lines.append(
            f"- {cell['mechanism_class']}"
            + (f" ({described})" if described else "")
            + f" - {sum(counts.values())} trials ({phase_mix or 'no phase data'}), "
            f"{counts.get('ACTIVE', 0)} active, "
            f"{cell.get('literature_support', 0)} matching abstracts"
        )
    return lines


def _briefing_context(
    mechanisms: list[dict],
    previously_attempted: list[dict],
    trials: list[dict],
    publications: list[dict],
    phases: dict,
    trend: dict,
    organizations: list[dict],
) -> str:
    """Aggregate the scan evidence the brief reports from.

    Compact by design: this travels to the client and back, so it carries
    aggregates plus a bounded sample of source text, not the full corpus.
    """
    parts: list[str] = []

    if mechanisms:
        parts.append(
            "MECHANISM CLASSES IN THE EXAMINED TRIALS AND LITERATURE "
            "(ordered by active trials):\n" + "\n".join(_mechanism_lines(mechanisms, 12))
        )
    if previously_attempted:
        parts.append(
            "MECHANISM CLASSES WITH A TERMINATED OR NEGATIVE TRIAL ON RECORD:\n"
            + "\n".join(_mechanism_lines(previously_attempted, 6))
        )

    counts = phases.get("counts") or {}
    if counts:
        parts.append(
            "TRIAL PHASE DISTRIBUTION "
            f"({phases.get('phased_trials', 0)} of {phases.get('total_trials', 0)} "
            "trials carry a phase; multi-phase trials count in each):\n"
            + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
            + "\n(UNSPECIFIED = observational or non-phased; NA = not applicable)"
        )

    years = trend.get("years") or {}
    if years:
        partial = trend.get("partial_year")
        series = ", ".join(
            f"{year}: {count}" + (" (year incomplete)" if int(year) == partial else "")
            for year, count in sorted(years.items())
        )
        parts.append("PUBLICATIONS PER YEAR (all PubMed records for the disease):\n" + series)

    if organizations:
        parts.append(
            "LEAD SPONSORS AND PATENT ASSIGNEES:\n"
            + ", ".join(
                f"{o['name']} ({o['trial_count']} trials, {o['patent_count']} patents)"
                for o in organizations[:10]
            )
        )

    stopped = [t for t in trials if t.get("status_class") in _STOPPED_STATUSES]
    if stopped:
        lines = []
        for t in stopped[:_STOPPED_TRIALS_IN_CONTEXT]:
            reason = t.get("why_stopped") or "no reason recorded in the registry"
            interventions = ", ".join((t.get("intervention_names") or [])[:3]) or "not listed"
            phase = "/".join(t.get("phases") or []) or "no phase"
            lines.append(
                f"- {t['nct_id']}: {t['brief_title']} [{t['status_class']}; {phase}; "
                f"interventions: {interventions}] Registered reason: {reason}"
            )
        parts.append(
            f"TRIALS TERMINATED, WITHDRAWN OR COMPLETED NEGATIVE ({len(stopped)} in the "
            "examined set):\n" + "\n".join(lines)
        )

    active = [t for t in trials if t.get("status_class") == "ACTIVE" and t.get("brief_title")]
    if active:
        lines = []
        for t in active[:10]:
            phase = "/".join(t.get("phases") or []) or "no phase"
            sponsor = f"; sponsor: {t['lead_sponsor']}" if t.get("lead_sponsor") else ""
            interventions = ", ".join((t.get("intervention_names") or [])[:3]) or "not listed"
            lines.append(
                f"- {t['nct_id']}: {t['brief_title']} [{phase}; interventions: "
                f"{interventions}{sponsor}]"
            )
        parts.append("ACTIVE TRIALS (sample):\n" + "\n".join(lines))

    sampled_pubs = [p for p in publications if p.get("abstract")][:10]
    if sampled_pubs:
        parts.append(
            "RECENT ABSTRACTS (sample):\n"
            + "\n".join(
                f"- PMID {p['pmid']}: {p['title']} - {p['abstract'][:320]}"
                for p in sampled_pubs
            )
        )

    return "\n\n".join(parts)


def _background_context(background: dict) -> str:
    """Format targeted background literature for the brief, labelled by facet."""
    parts = []
    for facet, label in _FACET_LABELS.items():
        records = background.get(facet) or []
        if not records:
            parts.append(f"{label}:\n(no abstracts retrieved)")
            continue
        lines = [
            f"- PMID {r['pmid']} ({(r.get('pub_date') or '')[:4] or 'n.d.'}): "
            f"{r['title']} - {r['abstract'][:900]}"
            for r in records
        ]
        parts.append(f"{label}:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _background_references(background: dict) -> list[dict]:
    return [
        {"pmid": r["pmid"], "title": r["title"], "facet": facet}
        for facet in _FACET_LABELS
        for r in (background.get(facet) or [])
    ]


def _unclassified_summary(cell: dict | None) -> dict | None:
    """Report the unclassified remainder as counts."""
    if not cell:
        return None
    return {
        "trial_count": sum(cell["trial_count_by_status"].values()),
        "publication_count": cell["publication_count"],
    }


def _attach_context(cells: list[dict], trials: list[dict], publications: list[dict]) -> None:
    """Attach the source text each cell would need for synthesis."""
    if not cells:
        return

    pubs_by_pmid = {p["pmid"]: p for p in publications if p.get("pmid")}
    trials_by_nct = {t["nct_id"]: t for t in trials if t["nct_id"]}

    for cell in cells:
        # Each source carries its own identifier: the prompts require every claim
        # to cite a PMID or NCT ID, and without them in the text the model can only
        # cite the position ("Publication 1"), which is untraceable.
        abstracts = [
            f"PMID {pmid}: {pubs_by_pmid[pmid]['abstract'] or pubs_by_pmid[pmid]['title']}"
            for pmid in cell["supporting_pmids"]
            if pmid in pubs_by_pmid
        ][:5]
        trial_summaries = [
            _trial_summary(nct_id, t)
            for nct_id in cell["supporting_nct_ids"]
            if (t := trials_by_nct.get(nct_id))
        ][:5]
        cell["context"] = {"abstracts": abstracts, "trial_summaries": trial_summaries}


def _trial_summary(nct_id: str, trial: dict) -> str:
    """One trial as a citable line, with the registered stop reason when present."""
    parts = [f"{nct_id}: {trial['brief_title']}.", f"Status: {trial['status_class']}."]
    if trial.get("phases"):
        parts.append(f"Phase: {'/'.join(trial['phases'])}.")
    if trial.get("why_stopped"):
        parts.append(f"Reason stopped: {trial['why_stopped']}.")
    if trial.get("lead_sponsor"):
        parts.append(f"Sponsor: {trial['lead_sponsor']}.")
    parts.append(trial["brief_summary"][:300])
    return " ".join(parts).strip()
