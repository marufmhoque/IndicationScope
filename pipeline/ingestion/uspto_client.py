"""USPTO PatentsView API client for patent data retrieval."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 5
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

PATENTS_VIEW_BASE = "https://api.patentsview.org/patents/query"


class USPTOClient:
    def __init__(self, base_url: str = PATENTS_VIEW_BASE):
        self.base_url = base_url

    def fetch_patents(self, disease: str) -> list[dict]:
        """Return patent records matching a disease query."""
        params = {
            "q": self._build_query(disease),
            "f": ["patent_number", "patent_title", "patent_abstract", "patent_date", "inventors"],
            "per_page": 100,
        }

        results: list[dict] = []
        page = 1

        while True:
            params["page"] = page

            self._rate_limit()
            resp = self._get_with_backoff(params)
            if resp.status_code != 200:
                logger.warning("USPTO API returned %d for disease=%r", resp.status_code, disease)
                break

            body = resp.json()
            patents = body.get("patents", [])
            if not patents:
                break

            results.extend(patents)
            logger.debug("Fetched page %d: %d patents, total so far: %d", page, len(patents), len(results))

            total_pages = body.get("total_page_count", page)
            if page >= total_pages:
                break
            page += 1

        logger.info(
            "USPTO fetch complete — disease=%r count=%d",
            disease, len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query(disease: str) -> str:
        """Build PatentsView query string for disease keyword."""
        return f'{{patent_abstract: "{disease}" OR patent_title: "{disease}"}}'

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
            try:
                resp = httpx.get(self.base_url, json=params, timeout=30)
                if resp.status_code == 429:
                    logger.warning("Rate-limited by USPTO — retrying in %.1fs (attempt %d)", delay, attempt + 1)
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                logger.warning("Timeout from USPTO — retrying in %.1fs (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
                delay = min(delay * 2, 60)
        logger.error("Failed to fetch from USPTO after %d retries", max_retries)
        return httpx.Response(503)  # Return error response
