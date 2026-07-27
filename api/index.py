from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="IndicationScope API")


class ScanRequest(BaseModel):
    disease: str
    mechanism: str | None = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scan")
def scan(body: ScanRequest):
    return {
        "disease": body.disease,
        "mechanism": body.mechanism,
        "results": [
            {
                "drug": "Example Drug A",
                "evidence_score": 0.87,
                "sources": ["PubMed:12345678", "ClinicalTrials:NCT0000001"],
                "summary": "Stub result — real extraction not yet implemented.",
            }
        ],
    }
