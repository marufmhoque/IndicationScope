"""Orchestrator for fetching data from multiple sources."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .clinicaltrials_client import ClinicalTrialsClient
from .pubmed_client import PubMedClient
from .uspto_client import USPTOClient
from .google_patents_client import GooglePatentsClient
from .cache import QueryCache

logger = logging.getLogger(__name__)

_SOURCE_NAMES = ("pubmed", "clinical_trials", "uspto", "google_patents")

# Not a source of records — a per-year count series for the momentum chart.
# Runs alongside the sources so its handful of small requests costs no extra
# wall-clock time.
_TREND_KEY = "publication_trend"


def _empty_source() -> dict:
    return {"total": 0, "records": []}


class IngestionOrchestrator:
    def __init__(self):
        self.pubmed = PubMedClient()
        self.clinical_trials = ClinicalTrialsClient()
        self.uspto = USPTOClient()
        self.google_patents = GooglePatentsClient()
        self.cache = QueryCache()

    def fetch_all_sources(self, disease: str, mechanism: str | None = None) -> dict:
        """Fetch from every source in parallel.

        Each source returns {"total", "records"}: the true match count, and the
        sample actually fetched for analysis. They differ by orders of magnitude
        for common diseases — see the individual clients.
        """
        query = {"disease": disease, "mechanism": mechanism}
        query_hash = QueryCache.make_hash(query)

        cached = self.cache.get(query_hash)
        if cached:
            logger.info("Returning cached results for disease=%r", disease)
            return cached

        results = {
            "query": query,
            "sources": {name: _empty_source() for name in _SOURCE_NAMES},
            _TREND_KEY: {"years": {}, "partial_year": 0},
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.pubmed.fetch_publications, disease): "pubmed",
                executor.submit(
                    self.clinical_trials.fetch_trials, disease, mechanism
                ): "clinical_trials",
                executor.submit(self.uspto.fetch_patents, disease): "uspto",
                executor.submit(self.google_patents.fetch_patents, disease): "google_patents",
                executor.submit(self.pubmed.fetch_year_counts, disease): _TREND_KEY,
            }

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    data = future.result()
                    if source_name == _TREND_KEY:
                        results[_TREND_KEY] = data
                        continue
                    results["sources"][source_name] = data
                    logger.info(
                        "Fetched %s for disease=%r — total=%d sampled=%d",
                        source_name, disease, data["total"], len(data["records"]),
                    )
                except Exception as exc:
                    # One dead source must not fail the scan; it degrades to zero.
                    logger.error("Failed to fetch from %s: %s", source_name, exc)
                    if source_name != _TREND_KEY:
                        results["sources"][source_name] = _empty_source()

        self.cache.set(query_hash, results)
        logger.info(
            "Ingestion complete for disease=%r — %d/%d sources returned records",
            disease,
            len([s for s in results["sources"].values() if s["records"]]),
            len(_SOURCE_NAMES),
        )
        return results
