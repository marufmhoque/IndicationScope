from datetime import datetime, timezone

from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

from pipeline.ingestion.orchestrator import IngestionOrchestrator

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
    # Fetch data from all sources
    ingestion_results = ingestion.fetch_all_sources(body.disease, body.mechanism)

    # TODO: Process results through scoring, normalization, and synthesis pipeline
    return {
        "query": {
            "disease": body.disease,
            "mechanism": body.mechanism,
            "persona": body.persona,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": ingestion_results["sources"],
        "candidates": [],
        "previously_attempted": [],
        "trial_count": len(ingestion_results["sources"].get("clinical_trials", [])),
        "publication_count": len(ingestion_results["sources"].get("pubmed", [])),
        "patent_count": len(ingestion_results["sources"].get("uspto", [])) + len(ingestion_results["sources"].get("google_patents", [])),
    }
