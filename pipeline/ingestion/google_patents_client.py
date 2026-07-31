"""Google Patents client using the patents.google.com JSON query endpoint."""

import html
import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 2
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

_MAX_PAGES = 5
_TAG_RE = re.compile(r"<[^>]+>")

GOOGLE_PATENTS_QUERY = "https://patents.google.com/xhr/query"


class GooglePatentsClient:
    """Reads the same JSON endpoint the Google Patents web UI calls.

    The HTML at patents.google.com is a JavaScript shell with no patent
    content in it, so the results are fetched from /xhr/query instead.
    """

    def __init__(self, base_url: str = GOOGLE_PATENTS_QUERY):
        self.base_url = base_url

    def fetch_patents(self, disease: str) -> list[dict]:
        """Return patent records matching a disease query."""
        results: list[dict] = []

        for page in range(_MAX_PAGES):
            query = f"q={disease}" + (f"&page={page}" if page else "")

            self._rate_limit()
            resp = self._get_with_backoff({"url": query})
            if resp is None:
                break

            body = resp.json().get("results", {})
            patents = self._parse(body)
            if not patents:
                break

            results.extend(patents)
            logger.debug(
                "Fetched page %d: %d patents, total so far: %d", page, len(patents), len(results)
            )

            if page + 1 >= body.get("total_num_pages", 0):
                break

        logger.info(
            "Google Patents fetch complete — disease=%r count=%d",
            disease, len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @classmethod
    def _parse(cls, body: dict) -> list[dict]:
        """Flatten the clustered result payload into patent records."""
        records: list[dict] = []
        for cluster in body.get("cluster", []):
            for item in cluster.get("result", []):
                patent = item.get("patent", {})
                number = patent.get("publication_number", "")
                if not number:
                    continue
                records.append(
                    {
                        "patent_number": number,
                        "patent_title": cls._clean(patent.get("title", "")),
                        "patent_abstract": cls._clean(patent.get("snippet", "")),
                        "patent_date": patent.get("publication_date", ""),
                        "filing_date": patent.get("filing_date", ""),
                        "priority_date": patent.get("priority_date", ""),
                        "assignee": patent.get("assignee", ""),
                        "inventor": patent.get("inventor", ""),
                        "url": f"https://patents.google.com/patent/{number}/en",
                        "source": "google_patents",
                    }
                )
        return records

    @staticmethod
    def _clean(text: str) -> str:
        """Strip the <b> match highlighting and decode HTML entities."""
        return html.unescape(_TAG_RE.sub("", text)).strip()

    @staticmethod
    def _rate_limit() -> None:
        global _last_call
        elapsed = time.monotonic() - _last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call = time.monotonic()

    def _get_with_backoff(self, params: dict, max_retries: int = 3) -> httpx.Response | None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        delay = 1.0
        for attempt in range(max_retries):
            try:
                resp = httpx.get(self.base_url, params=params, headers=headers, timeout=30)
                # /xhr/query is undocumented and throttles by IP, answering 503
                # once a burst trips its limit. Both codes mean "back off".
                if resp.status_code in (429, 503):
                    logger.warning(
                        "Throttled by Google Patents (HTTP %d) — retrying in %.1fs (attempt %d)",
                        resp.status_code, delay, attempt + 1,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "Google Patents request failed (%s) — retrying in %.1fs (attempt %d)",
                    type(exc).__name__, delay, attempt + 1,
                )
                time.sleep(delay)
                delay = min(delay * 2, 60)

        logger.error(
            "Google Patents unavailable after %d retries — likely IP throttling; "
            "results will omit this source",
            max_retries,
        )
        return None
