from datetime import datetime, timezone

from fastapi import FastAPI
from mangum import Mangum
from pydantic import BaseModel

app = FastAPI(title="IndicationScope API")
handler = Mangum(app, lifespan="off")


class ScanRequest(BaseModel):
    disease: str
    mechanism: str | None = None
    persona: str = "academic"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan")
def scan(body: ScanRequest):
    # TODO: replace mock with pipeline.run(body.disease, body.mechanism, body.persona)
    return {
        "query": {
            "disease": body.disease,
            "mechanism": body.mechanism,
            "persona": body.persona,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": [],
        "previously_attempted": [],
        "trial_count": 0,
        "publication_count": 0,
    }
