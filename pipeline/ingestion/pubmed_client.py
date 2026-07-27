"""PubMed client using Biopython Entrez."""

import logging
import os

from Bio import Entrez

logger = logging.getLogger(__name__)

_MAX_RESULTS = 500


class PubMedClient:
    def __init__(self):
        Entrez.email = "indicationscope@example.com"
        api_key = os.getenv("NCBI_API_KEY")
        if api_key:
            Entrez.api_key = api_key

    def fetch_publications(self, disease: str) -> list[dict]:
        """Return publication records for a disease query."""
        pmids = self._search(disease)
        if not pmids:
            logger.info("PubMed: no results for %r", disease)
            return []

        records = self._fetch_records(pmids)
        logger.info("PubMed fetch complete — disease=%r count=%d", disease, len(records))
        return records

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _search(self, query: str) -> list[str]:
        handle = Entrez.esearch(db="pubmed", term=query, retmax=_MAX_RESULTS)
        result = Entrez.read(handle)
        handle.close()
        return result.get("IdList", [])

    def _fetch_records(self, pmids: list[str]) -> list[dict]:
        if not pmids:
            return []

        handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="xml",
            retmode="xml",
        )
        raw = Entrez.read(handle)
        handle.close()

        results: list[dict] = []
        for article in raw.get("PubmedArticle", []):
            medline = article.get("MedlineCitation", {})
            art = medline.get("Article", {})

            # TODO: full abstract extraction (ArticleAbstract → AbstractText list)
            # TODO: MeSH heading extraction
            # TODO: publication type list
            results.append(
                {
                    "pmid": str(medline.get("PMID", "")),
                    "title": str(art.get("ArticleTitle", "")),
                    "abstract": "",
                    "mesh_terms": [],
                    "mechanism_class": [],
                    "condition_normalized": [],
                    "pub_date": "",
                    "publication_type": [],
                }
            )
        return results
