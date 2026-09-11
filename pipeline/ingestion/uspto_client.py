"""USPTO Open Data Portal client.

The legacy PatentsView API (api.patentsview.org) was retired and now
redirects to data.uspto.gov. Its replacement requires a free API key,
requested at https://data.uspto.gov/ and supplied via USPTO_API_KEY.
Without a key this client returns no records rather than failing the run.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 5
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

_PAGE_SIZE = 100
_MAX_PAGES = 5

USPTO_SEARCH_URL = "https://api.uspto.gov/api/v1/patent/applications/search"


class USPTOClient:
    def __init__(self, base_url: str = USPTO_SEARCH_URL, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key or os.getenv("USPTO_API_KEY")

    def fetch_patents(self, disease: str) -> dict:
        """Return {"total": int, "records": list[dict]} for a disease query."""
        if not self.api_key:
            logger.warning(
                "USPTO skipped — set USPTO_API_KEY (free key from https://data.uspto.gov/) to enable"
            )
            return {"total": 0, "records": []}

        results: list[dict] = []
        total = 0

        for page in range(_MAX_PAGES):
            params = {
                "q": disease,
                "limit": _PAGE_SIZE,
                "offset": page * _PAGE_SIZE,
            }

            self._rate_limit()
            resp = self._get_with_backoff(params)
            if resp is None:
                break

            body = resp.json()
            total = body.get("count", total)
            patents = self._parse(body)
            if not patents:
                break

            results.extend(patents)
            logger.debug(
                "Fetched page %d: %d patents, total so far: %d", page, len(patents), len(results)
            )

            if len(results) >= body.get("count", 0):
                break

        logger.info(
            "USPTO fetch complete — disease=%r total=%d sampled=%d",
            disease, total, len(results),
        )
        return {"total": total or len(results), "records": results}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(body: dict) -> list[dict]:
        records: list[dict] = []
        for item in body.get("patentFileWrapperDataBag", []):
            meta = item.get("applicationMetaData", {})
            number = item.get("applicationNumberText", "")
            if not number:
                continue
            records.append(
                {
                    "patent_number": meta.get("patentNumber", "") or number,
                    "patent_title": meta.get("inventionTitle", ""),
                    "patent_abstract": "",
                    "patent_date": meta.get("grantDate", "") or meta.get("filingDate", ""),
                    "filing_date": meta.get("filingDate", ""),
                    "assignee": meta.get("firstApplicantName", ""),
                    "inventor": meta.get("firstInventorName", ""),
                    "url": f"https://patentcenter.uspto.gov/applications/{number}",
                    "source": "uspto",
                }
            )
        return records

    @staticmethod
    def _rate_limit() -> None:
        global _last_call
        elapsed = time.monotonic() - _last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call = time.monotonic()

    def _get_with_backoff(self, params: dict, max_retries: int = 3) -> httpx.Response | None:
        headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        delay = 1.0
        for attempt in range(max_retries):
            try:
                resp = httpx.get(self.base_url, params=params, headers=headers, timeout=30)
                if resp.status_code in (401, 403):
                    logger.error("USPTO rejected the API key (HTTP %d)", resp.status_code)
                    return None
                if resp.status_code == 429:
                    logger.warning(
                        "Rate-limited by USPTO — retrying in %.1fs (attempt %d)", delay, attempt + 1
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "USPTO request failed (%s) — retrying in %.1fs (attempt %d)",
                    type(exc).__name__, delay, attempt + 1,
                )
                time.sleep(delay)
                delay = min(delay * 2, 60)

        logger.error("Failed to fetch from USPTO after %d retries", max_retries)
        return None
