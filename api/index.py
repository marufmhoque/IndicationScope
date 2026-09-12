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
from pipeline.scoring.matrix_builder import build_matrix
from pipeline.scoring.white_space_score import rank_by_activity, rank_cells
from pipeline.synthesis.rationale_generator import (
    DEFAULT_PERSONA,
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
# Below this much remaining time, skip LLM classification entirely — counts and
# scores still come back, everything just lands in "Unclassified".
_MIN_EXTRACTION_S = 12

# Mechanisms shown in the Standard of Care view.
_SOC_TOP_N = 12
# Measured extraction throughput (16 workers, ~0.85s per call). Only used to
# size the item cap against the remaining budget.
_ITEMS_PER_SECOND = 14

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
    # Captured for the response echo only. Persona is a synthesis lens, so it
    # deliberately does not affect ingestion, scoring, or what is searched.
    persona: str = DEFAULT_PERSONA


class SynthesisRequest(BaseModel):
    """Stateless: the client passes back the context /api/scan gave it.

    Re-deriving context server-side would mean re-running ingestion, and the
    serverless cache is per-instance — a cold instance would refetch everything.
    """

    mechanism_class: str
    indication: str
    persona: str = DEFAULT_PERSONA
    supporting_pmids: list[str] = []
    supporting_nct_ids: list[str] = []
    abstracts: list[str] = []
    trial_summaries: list[str] = []


class BriefingRequest(BaseModel):
    """Stateless like the other synthesis endpoints.

    /api/scan hands the client the aggregated evidence and it comes back here,
    so a cold instance never has to re-run ingestion to write the briefing.
    """

    indication: str
    context: str
    coverage_note: str = ""
    persona: str = DEFAULT_PERSONA


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
    candidates, previously_attempted, unclassified = rank_cells(matrix["cells"])
    standard_of_care = rank_by_activity(matrix["cells"])[:_SOC_TOP_N]
    organizations = aggregate_organizations(trials, patents, limit=30)

    # Both sections can request synthesis, so both need their source text.
    _attach_context(candidates[:SYNTHESIS_TOP_N], trials, publications)
    _attach_context(previously_attempted[:SYNTHESIS_TOP_N], trials, publications)

    logger.info(
        "Scan complete — disease=%r candidates=%d prior=%d elapsed=%.1fs",
        body.disease, len(candidates), len(previously_attempted),
        time.monotonic() - started,
    )

    return {
        "query": {
            "disease": body.disease,
            "mechanism": body.mechanism,
            "persona": body.persona,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "previously_attempted": previously_attempted,
        # What the classification budget didn't reach. Surfaced rather than
        # ranked: it holds the most records and would otherwise top the list,
        # presenting "not looked at" as the strongest opportunity.
        "unclassified": _unclassified_summary(unclassified),
        "coverage": matrix["coverage"],
        "standard_of_care": standard_of_care,
        "phase_distribution": _phase_distribution(trials),
        "publication_trend": ingested.get("publication_trend", {"years": {}, "partial_year": 0}),
        # How much of each corpus the analysis actually saw. This ranges from
        # 1.7% (type 2 diabetes) to 100% (rare indications), and a landscape
        # built on a fiftieth of the record is a different claim from one built
        # on all of it — the UI scales its caveat to this.
        "sampling": {
            "trials": _fraction(len(trials), ct["total"]),
            "publications": _fraction(len(publications), pubmed["total"]),
        },
        "briefing_context": _briefing_context(
            standard_of_care, candidates, previously_attempted, trials,
            publications, _phase_distribution(trials),
            ingested.get("publication_trend", {}), organizations,
        ),
        "coverage_note": _coverage_note(
            _fraction(len(trials), ct["total"]),
            _fraction(len(publications), pubmed["total"]),
        ),
        # Ranked across both kinds, so ask for enough that academic sponsors
        # survive an industry-heavy field; the UI caps each kind separately.
        "key_organizations": organizations,
        "key_researchers": aggregate_researchers(publications),
        # *_count is the true number of matches; *_analyzed is what was actually
        # ingested. They differ by orders of magnitude for common diseases.
        "trial_count": ct["total"],
        "trials_analyzed": len(trials),
        "publication_count": pubmed["total"],
        "publications_analyzed": len(publications),
        "patent_count": sources["uspto"]["total"] + sources["google_patents"]["total"],
        "patents_analyzed": len(patents),
    }


@router.post("/rationale")
def rationale(body: SynthesisRequest):
    """Synthesise one cell's white-space rationale.

    Split out of /scan because synthesis is the single most expensive step and
    would otherwise push a scan past the platform's function timeout.
    """
    return generate_rationale(
        _cell_from(body), body.abstracts, body.trial_summaries, persona=body.persona
    )


@router.post("/failure-analysis")
def failure_analysis(body: SynthesisRequest):
    """Explain why prior attempts at one mechanism-indication pair failed.

    Runs on demand rather than during the scan: most failed mechanisms are never
    expanded, and generating for all of them would cost a call each for nothing.
    """
    return generate_failure_analysis(
        _cell_from(body), body.abstracts, body.trial_summaries, persona=body.persona
    )


@router.post("/briefing")
def briefing(body: BriefingRequest):
    """Write the executive landscape briefing.

    Runs on demand rather than inside /api/scan: it is the largest single model
    call in the app, and the scan already carries ingestion plus classification
    against the platform's function timeout.
    """
    cache = get_briefing_cache()
    cached = cache.get(body.indication)
    if cached:
        logger.info("Briefing cache hit for %r", body.indication)
        return cached

    result = generate_executive_briefing(
        body.indication, body.context, body.coverage_note, persona=body.persona
    )
    # Only cache a briefing that actually said something; caching an all-null
    # result would make a transient failure permanent.
    if any(result.values()):
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

    A trial registered as PHASE1|PHASE2 contributes to both buckets, so the
    counts sum to more than the number of trials. The totals travel alongside
    so the UI can label the chart without implying the bars are a trial count.

    Trials with no phase get their own bucket rather than being dropped:
    availability swings 46-87% by disease (observational studies carry none),
    so omitting them would understate the field.
    """
    counts: dict[str, int] = {}
    phased = 0
    for trial in trials:
        phases = trial.get("phases") or []
        if phases:
            phased += 1
        for phase in phases or ["UNSPECIFIED"]:
            counts[phase] = counts.get(phase, 0) + 1
    return {
        "counts": counts,
        "phased_trials": phased,
        "total_trials": len(trials),
    }


def _coverage_note(trials: dict, publications: dict) -> str:
    """One sentence telling the model how much of the record it is seeing.

    Coverage ranges from 1.7% of registered trials (type 2 diabetes) to 100%
    (rare indications). Without this the model writes with identical authority
    either way, which is exactly wrong for the low-coverage case.
    """
    return (
        f"This analysis examined {trials['ingested']} of {trials['total']} registered "
        f"trials ({_percent(trials['fraction'])}) and {publications['ingested']} of "
        f"{publications['total']} publications ({_percent(publications['fraction'])}). "
        "Calibrate every claim to that coverage."
    )


def _percent(fraction: float) -> str:
    """Format a coverage share.

    A small nonzero fraction must not round to "0%": for a large indication the
    publication sample really is a fraction of a percent, and "0%" reads as
    having looked at nothing at all.
    """
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
        failure = ", prior failure on record" if cell.get("has_prior_failure") else ""
        lines.append(
            f"- {cell['mechanism_class']} [{cell.get('pillar') or 'Other'}] - "
            f"{sum(counts.values())} trials ({phase_mix or 'no phase data'}), "
            f"{cell.get('literature_support', 0)} supporting abstracts{failure}"
        )
    return lines


def _briefing_context(
    standard_of_care: list[dict],
    candidates: list[dict],
    previously_attempted: list[dict],
    trials: list[dict],
    publications: list[dict],
    phases: dict,
    trend: dict,
    organizations: list[dict],
) -> str:
    """Aggregate the evidence the briefing reasons over.

    Deliberately compact: this travels to the client and back, so it carries
    aggregates plus a bounded sample of source text, not the full corpus.
    """
    parts: list[str] = []

    if standard_of_care:
        parts.append(
            "MOST-TESTED MECHANISMS:\n" + "\n".join(_mechanism_lines(standard_of_care, 10))
        )
    if candidates:
        parts.append(
            "LEAST-CONTESTED MECHANISMS:\n" + "\n".join(_mechanism_lines(candidates, 8))
        )
    if previously_attempted:
        parts.append(
            "MECHANISMS WITH PRIOR FAILURES:\n"
            + "\n".join(_mechanism_lines(previously_attempted, 5))
        )

    if phases:
        parts.append(
            "TRIAL PHASE DISTRIBUTION:\n"
            + ", ".join(f"{k}: {v}" for k, v in sorted(phases.items()))
            + "\n(UNSPECIFIED = observational or non-phased; NA = not applicable)"
        )

    years = trend.get("years") or {}
    if years:
        partial = trend.get("partial_year")
        series = ", ".join(
            f"{year}: {count}" + (" (year incomplete)" if int(year) == partial else "")
            for year, count in sorted(years.items())
        )
        parts.append("PUBLICATIONS PER YEAR:\n" + series)

    if organizations:
        parts.append(
            "LEADING ORGANISATIONS:\n"
            + ", ".join(
                f"{o['name']} ({o['trial_count']} trials)" for o in organizations[:8]
            )
        )

    sampled_trials = [t for t in trials if t.get("brief_title")][:8]
    if sampled_trials:
        lines = []
        for t in sampled_trials:
            stopped = f" stopped: {t['why_stopped']}" if t.get("why_stopped") else ""
            lines.append(
                f"- {t['nct_id']}: {t['brief_title']} [{t['status_class']}]{stopped}"
            )
        parts.append("SAMPLE TRIALS:\n" + "\n".join(lines))

    sampled_pubs = [p for p in publications if p.get("abstract")][:8]
    if sampled_pubs:
        parts.append(
            "SAMPLE ABSTRACTS:\n"
            + "\n".join(
                f"- PMID {p['pmid']}: {p['title']} - {p['abstract'][:320]}"
                for p in sampled_pubs
            )
        )

    return "\n\n".join(parts)


def _unclassified_summary(cell: dict | None) -> dict | None:
    """Report the unclassified remainder as counts, not as a pseudo-candidate."""
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
        # Each source carries its own identifier: the prompts require every
        # claim to cite a PMID or NCT ID, and without them in the text the model
        # can only cite the position ("Publication 1"), which is untraceable.
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
    """One trial as a citable line.

    why_stopped is included verbatim when present — it is the only record of why
    a trial actually stopped, and the failure analysis has nothing to work from
    without it.
    """
    parts = [f"{nct_id}: {trial['brief_title']}.", f"Status: {trial['status_class']}."]
    if trial.get("why_stopped"):
        parts.append(f"Reason stopped: {trial['why_stopped']}.")
    if trial.get("lead_sponsor"):
        parts.append(f"Sponsor: {trial['lead_sponsor']}.")
    parts.append(trial["brief_summary"][:300])
    return " ".join(parts).strip()
