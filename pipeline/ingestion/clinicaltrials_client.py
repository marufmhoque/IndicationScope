"""ClinicalTrials.gov v2 API client with pagination and rate limiting."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 5
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

CT_GOV_BASE = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsClient:
    def __init__(self, base_url: str = CT_GOV_BASE):
        self.base_url = base_url

    def fetch_trials(self, disease: str, mechanism: str | None = None) -> list[dict]:
        """Return all trial records matching disease (+optional mechanism)."""
        params: dict = {
            "query.cond": disease,
            "pageSize": 100,
            "format": "json",
        }
        if mechanism:
            params["query.intr"] = mechanism

        results: list[dict] = []
        next_token: str | None = None

        while True:
            if next_token:
                params["pageToken"] = next_token

            self._rate_limit()
            resp = self._get_with_backoff(params)
            body = resp.json()

            studies = body.get("studies", [])
            results.extend(studies)
            logger.debug("Fetched page: %d studies, total so far: %d", len(studies), len(results))

            next_token = body.get("nextPageToken")
            if not next_token:
                break

        logger.info(
            "ClinicalTrials fetch complete — disease=%r mechanism=%r count=%d",
            disease, mechanism, len(results),
        )
        return results

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

    def _get_with_backoff(self, params: dict, max_retries: int = 6) -> httpx.Response:
        delay = 1.0
        for attempt in range(max_retries):
            resp = httpx.get(self.base_url, params=params, timeout=30)
            if resp.status_code == 429:
                logger.warning("Rate-limited by CT.gov — retrying in %.1fs (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"CT.gov returned 429 after {max_retries} retries")
