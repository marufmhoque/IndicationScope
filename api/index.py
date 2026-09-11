import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

# Nothing else loaded .env.local — locally-run uvicorn never saw
# ANTHROPIC_API_KEY/NCBI_API_KEY without this. Must run before the clients
# below read those vars at import/construction time. A no-op in deployed
# environments (Vercel), which inject real env vars instead of this file.
load_dotenv(".env.local")

from fastapi import APIRouter, FastAPI
from mangum import Mangum
from pydantic import BaseModel

from pipeline.ingestion.orchestrator import IngestionOrchestrator
from pipeline.normalization.trial_normalizer import normalize_trial
from pipeline.scoring.matrix_builder import build_matrix
from pipeline.scoring.white_space_score import rank_cells
from pipeline.synthesis.rationale_generator import generate_rationale

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
# Rough extraction throughput (8 workers, ~1.5s per call). Only used to size the
# item cap against the remaining budget.
_ITEMS_PER_SECOND = 5

# Only the top candidates carry synthesis context back to the client, to keep the
# response small. These are the ones the UI requests rationales for.
_CONTEXT_TOP_N = 5

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
    persona: str = "academic"


class RationaleRequest(BaseModel):
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

    trials = [normalize_trial(t) for t in ct["records"]]

    cells = build_matrix(
        trials,
        publications,
        indication=body.disease,
        max_extraction_items=_extraction_budget(started),
    )
    candidates, previously_attempted = rank_cells(cells)
    _attach_context(candidates[:_CONTEXT_TOP_N], trials, publications)

    logger.info(
        "Scan complete — disease=%r candidates=%d elapsed=%.1fs",
        body.disease, len(candidates), time.monotonic() - started,
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
        # *_count is the true number of matches; *_analyzed is what was actually
        # classified. They differ by orders of magnitude for common diseases, so
        # the UI must not present the total as though it were all analysed.
        "trial_count": ct["total"],
        "trials_analyzed": len(trials),
        "publication_count": pubmed["total"],
        "publications_analyzed": len(publications),
        "patent_count": sources["uspto"]["total"] + sources["google_patents"]["total"],
        "patents_analyzed": (
            len(sources["uspto"]["records"]) + len(sources["google_patents"]["records"])
        ),
    }


@router.post("/rationale")
def rationale(body: RationaleRequest):
    """Synthesise one cell's rationale.

    Split out of /scan because synthesis is the single most expensive step and
    would otherwise push a scan past the platform's function timeout.
    """
    cell = {
        "mechanism_class": body.mechanism_class,
        "indication": body.indication,
        "supporting_pmids": body.supporting_pmids,
        "supporting_nct_ids": body.supporting_nct_ids,
    }
    return generate_rationale(cell, body.abstracts, body.trial_summaries)


# Vercel rewrites preserve the original request path, so in production the
# function sees the basePath-prefixed URL. Mounting both keeps local dev (where
# Next strips the prefix before proxying) working against the same code.
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/tools/indicationscope/api")


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

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


def _attach_context(candidates: list[dict], trials: list[dict], publications: list[dict]) -> None:
    """Attach the source text each candidate would need for synthesis."""
    if not candidates:
        return

    pubs_by_pmid = {p["pmid"]: p for p in publications if p.get("pmid")}
    trials_by_nct = {t["nct_id"]: t for t in trials if t["nct_id"]}

    for cell in candidates:
        # Each source carries its own identifier: the synthesis prompt requires
        # every claim to cite a PMID or NCT ID, and without them in the text the
        # model can only cite the position ("Publication 1"), which is untraceable.
        abstracts = [
            f"PMID {pmid}: {pubs_by_pmid[pmid]['abstract'] or pubs_by_pmid[pmid]['title']}"
            for pmid in cell["supporting_pmids"]
            if pmid in pubs_by_pmid
        ][:5]
        trial_summaries = [
            f"{nct_id}: {t['brief_title']}. Status: {t['status_class']}. "
            f"{t['brief_summary'][:300]}"
            for nct_id in cell["supporting_nct_ids"]
            if (t := trials_by_nct.get(nct_id))
        ][:5]
        cell["context"] = {"abstracts": abstracts, "trial_summaries": trial_summaries}
