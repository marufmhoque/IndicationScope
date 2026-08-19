from datetime import datetime, timezone

from dotenv import load_dotenv

# Nothing else loaded .env.local — locally-run uvicorn never saw
# ANTHROPIC_API_KEY/NCBI_API_KEY without this. Must run before the clients
# below read those vars at import/construction time. A no-op in deployed
# environments (Vercel), which inject real env vars instead of this file.
load_dotenv(".env.local")

from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

from config import SYNTHESIS_TOP_N
from pipeline.ingestion.orchestrator import IngestionOrchestrator
from pipeline.normalization.trial_normalizer import normalize_trial
from pipeline.scoring.matrix_builder import build_matrix
from pipeline.scoring.white_space_score import rank_cells
from pipeline.synthesis.rationale_generator import generate_rationale

app = FastAPI(title="IndicationScope API")
handler = Mangum(app, lifespan="off")

# Initialize ingestion orchestrator
ingestion = IngestionOrchestrator()


class ScanRequest(BaseModel):
    disease: str
    mechanism: str | None = None
    persona: str = "academic"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan")
def scan(body: ScanRequest):
    ingestion_results = ingestion.fetch_all_sources(body.disease, body.mechanism)
    sources = ingestion_results["sources"]
    raw_trials = sources.get("clinical_trials", [])
    publications = sources.get("pubmed", [])

    trials = [normalize_trial(t) for t in raw_trials]
    cells = build_matrix(trials, publications, indication=body.disease)
    candidates, previously_attempted = rank_cells(cells)
    _synthesize_top_candidates(candidates, trials, publications)

    return {
        "query": {
            "disease": body.disease,
            "mechanism": body.mechanism,
            "persona": body.persona,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "candidates": candidates,
        "previously_attempted": previously_attempted,
        "trial_count": len(raw_trials),
        "publication_count": len(publications),
        "patent_count": len(sources.get("uspto", [])) + len(sources.get("google_patents", [])),
    }


def _synthesize_top_candidates(
    candidates: list[dict], trials: list[dict], publications: list[dict]
) -> None:
    """Fill in `rationale` for the top SYNTHESIS_TOP_N candidates, in place."""
    if not candidates:
        return

    pubs_by_pmid = {p["pmid"]: p for p in publications if p.get("pmid")}
    trials_by_nct = {t["nct_id"]: t for t in trials if t["nct_id"]}

    for cell in candidates[:SYNTHESIS_TOP_N]:
        abstracts = [
            pubs_by_pmid[pmid]["abstract"] or pubs_by_pmid[pmid]["title"]
            for pmid in cell["supporting_pmids"]
            if pmid in pubs_by_pmid
        ][:5]
        trial_summaries = [
            f"{t['brief_title']}. Status: {t['status_class']}. {t['brief_summary'][:300]}"
            for nct_id in cell["supporting_nct_ids"]
            if (t := trials_by_nct.get(nct_id))
        ][:5]

        result = generate_rationale(cell, abstracts, trial_summaries)
        cell["rationale"] = result["rationale"]
        cell["supporting_pmids"] = result["supporting_pmids"]
        cell["supporting_nct_ids"] = result["supporting_nct_ids"]
