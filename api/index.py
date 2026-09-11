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

from pipeline.ingestion.orchestrator import IngestionOrchestrator
from pipeline.normalization.entity_aggregator import (
    aggregate_organizations,
    aggregate_researchers,
)
from pipeline.normalization.trial_normalizer import normalize_trial
from pipeline.scoring.matrix_builder import build_matrix
from pipeline.scoring.white_space_score import rank_cells
from pipeline.synthesis.rationale_generator import (
    DEFAULT_PERSONA,
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
# Measured extraction throughput (16 workers, ~0.85s per call). Only used to
# size the item cap against the remaining budget.
_ITEMS_PER_SECOND = 14

# Constructed on first use, not at import. Module-scope construction meant any
# init failure (e.g. a read-only filesystem) became a boot-time 500 on every route.
_ingestion: IngestionOrchestrator | None = None


def get_ingestion() -> IngestionOrchestrator:
    global _ingestion
    if _ingestion is None:
        _ingestion = IngestionOrchestrator()
    return _ingestion


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


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/scan")
def scan(body: ScanRequest):
    started = time.monotonic()

    sources = get_ingestion().fetch_all_sources(body.disease, body.mechanism)["sources"]
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
        # Ranked across both kinds, so ask for enough that academic sponsors
        # survive an industry-heavy field; the UI caps each kind separately.
        "key_organizations": aggregate_organizations(trials, patents, limit=30),
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
