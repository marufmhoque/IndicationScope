"""Google Patents web scraper client for patent data retrieval."""

import logging
import time
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPS = 2
_MIN_INTERVAL = 1.0 / _RATE_LIMIT_RPS
_last_call: float = 0.0

GOOGLE_PATENTS_BASE = "https://patents.google.com"
GOOGLE_PATENTS_SEARCH = f"{GOOGLE_PATENTS_BASE}/?q="


class GooglePatentsClient:
    def __init__(self, base_url: str = GOOGLE_PATENTS_BASE):
        self.base_url = base_url

    def fetch_patents(self, disease: str) -> list[dict]:
        """Return patent records matching a disease query from Google Patents."""
        search_url = f"{GOOGLE_PATENTS_SEARCH}{quote(disease)}"

        results: list[dict] = []
        page = 0
        max_pages = 5  # Limit to avoid excessive scraping

        while page < max_pages:
            self._rate_limit()
            url = search_url + (f"&page={page}" if page > 0 else "")

            resp = self._get_with_backoff(url)
            if resp.status_code != 200:
                logger.warning("Google Patents returned %d for disease=%r", resp.status_code, disease)
                break

            # Parse results from the page
            # Google Patents uses JavaScript rendering, so this is a best-effort extraction
            patents = self._parse_search_results(resp.text)
            if not patents:
                break

            results.extend(patents)
            logger.debug("Fetched page %d: %d patents, total so far: %d", page, len(patents), len(results))

            page += 1

        logger.info(
            "Google Patents fetch complete — disease=%r count=%d",
            disease, len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_search_results(html: str) -> list[dict]:
        """Extract patent data from search results HTML."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup4 is required for Google Patents scraping")
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []

        # Google Patents uses data attributes and dynamic content
        # This is a fallback extraction from visible HTML
        patent_items = soup.find_all("div", class_="result")
        if not patent_items:
            # Try alternative selectors
            patent_items = soup.find_all("div", attrs={"class": lambda x: x and "item" in x})

        for item in patent_items[:100]:  # Limit to 100 per page
            try:
                # Try to extract patent data
                title_elem = item.find("a", class_="title")
                abstract_elem = item.find("p", class_="abstract")
                id_elem = item.find("span", class_="patent-id")

                patent_data = {
                    "patent_number": id_elem.get_text(strip=True) if id_elem else "",
                    "patent_title": title_elem.get_text(strip=True) if title_elem else "",
                    "patent_abstract": abstract_elem.get_text(strip=True) if abstract_elem else "",
                    "patent_date": "",
                    "assignee": "",
                    "url": title_elem["href"] if title_elem and "href" in title_elem.attrs else "",
                }

                if patent_data.get("patent_number"):
                    results.append(patent_data)
            except (AttributeError, KeyError, TypeError):
                # Skip items that don't have required structure
                continue

        return results

    @staticmethod
    def _rate_limit() -> None:
        global _last_call
        elapsed = time.monotonic() - _last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call = time.monotonic()

    def _get_with_backoff(self, url: str, max_retries: int = 3) -> httpx.Response:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        delay = 1.0
        for attempt in range(max_retries):
            try:
                resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                if resp.status_code == 429:
                    logger.warning("Rate-limited by Google Patents — retrying in %.1fs (attempt %d)", delay, attempt + 1)
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                logger.warning("Timeout from Google Patents — retrying in %.1fs (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
                delay = min(delay * 2, 60)
        logger.error("Failed to fetch from Google Patents after %d retries", max_retries)
        return httpx.Response(503)  # Return error response
