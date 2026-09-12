"""ClinicalTrials.gov v2 API client.

Fetches one page of studies plus the *true* total. A common condition like
"diabetes" matches tens of thousands of studies; paginating all of them blows the
serverless time budget, and `countTotal` returns the real figure in the same
request — so the count stays accurate while only a sample is analysed.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 5
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

# Studies fetched for analysis. The reported total is the real count, not this —
# see the module docstring.
_SAMPLE_SIZE = 200

# Request only the fields actually consumed. Unmasked, 200 studies is ~5.4MB of
# JSON; masked it is ~213KB and arrives faster than 100 unmasked ones did. The
# response keeps the same nested protocolSection shape, so normalize_trial is
# unaffected. Any field added here must also be read there to be worth fetching.
_FIELDS = "|".join([
    "NCTId",
    "BriefTitle",
    "BriefSummary",
    "OverallStatus",
    "Phase",
    "WhyStopped",
    "Condition",
    "InterventionName",
    "LeadSponsorName",
    "HasResults",
])

CT_GOV_BASE = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsClient:
    def __init__(self, base_url: str = CT_GOV_BASE):
        self.base_url = base_url

    def fetch_trials(self, disease: str, mechanism: str | None = None) -> dict:
        """Return {"total": int, "records": list[dict]} for a disease query."""
        params: dict = {
            "query.cond": disease,
            "pageSize": _SAMPLE_SIZE,
            "format": "json",
            "countTotal": "true",
            "fields": _FIELDS,
        }
        if mechanism:
            params["query.intr"] = mechanism

        self._rate_limit()
        resp = self._get_with_backoff(params)
        body = resp.json()

        records = body.get("studies", [])
        total = body.get("totalCount", len(records))

        logger.info(
            "ClinicalTrials fetch complete — disease=%r mechanism=%r total=%d sampled=%d",
            disease, mechanism, total, len(records),
        )
        return {"total": total, "records": records}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _rate_limit() -> None:
        global _last_call
        elapsed = time.monotonic() - _last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call = time.monotonic()

    def _get_with_backoff(self, params: dict, max_retries: int = 3) -> httpx.Response:
        delay = 1.0
        for attempt in range(max_retries):
            resp = httpx.get(self.base_url, params=params, timeout=20)
            if resp.status_code == 429:
                logger.warning(
                    "Rate-limited by CT.gov — retrying in %.1fs (attempt %d)", delay, attempt + 1
                )
                time.sleep(delay)
                delay = min(delay * 2, 10)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"CT.gov returned 429 after {max_retries} retries")
