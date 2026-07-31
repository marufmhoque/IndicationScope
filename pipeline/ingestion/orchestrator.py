"""Orchestrator for fetching data from multiple sources."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .clinicaltrials_client import ClinicalTrialsClient
from .pubmed_client import PubMedClient
from .uspto_client import USPTOClient
from .google_patents_client import GooglePatentsClient
from .cache import QueryCache

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    def __init__(self):
        self.pubmed = PubMedClient()
        self.clinical_trials = ClinicalTrialsClient()
        self.uspto = USPTOClient()
        self.google_patents = GooglePatentsClient()
        self.cache = QueryCache()

    def fetch_all_sources(self, disease: str, mechanism: str | None = None) -> dict:
        """Fetch data from all available sources in parallel."""
        query = {"disease": disease, "mechanism": mechanism}
        query_hash = QueryCache.make_hash(query)

        # Check cache first
        cached = self.cache.get(query_hash)
        if cached:
            logger.info("Returning cached results for disease=%r", disease)
            return cached

        results = {
            "query": query,
            "sources": {
                "pubmed": [],
                "clinical_trials": [],
                "uspto": [],
                "google_patents": [],
            },
        }

        # Fetch from all sources in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.pubmed.fetch_publications, disease): "pubmed",
                executor.submit(
                    self.clinical_trials.fetch_trials, disease, mechanism
                ): "clinical_trials",
                executor.submit(self.uspto.fetch_patents, disease): "uspto",
                executor.submit(self.google_patents.fetch_patents, disease): "google_patents",
            }

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    data = future.result()
                    results["sources"][source_name] = data
                    logger.info(
                        "Fetched %d records from %s for disease=%r",
                        len(data),
                        source_name,
                        disease,
                    )
                except Exception as e:
                    logger.error("Failed to fetch from %s: %s", source_name, e)
                    results["sources"][source_name] = []

        # Cache results
        self.cache.set(query_hash, results)
        logger.info(
            "Ingestion complete for disease=%r — total sources: %d",
            disease,
            len([s for s in results["sources"].values() if s]),
        )
        return results
