"""PubMed client using Biopython Entrez.

esearch reports the true match count while honouring a small retmax, so the
headline number stays accurate while only a sample is efetch'd. Fetching the
full record set was the slowest step in a scan and returned multi-MB of XML
that was never used.
"""

import logging
import os

from Bio import Entrez

logger = logging.getLogger(__name__)

# Records actually fetched for mechanism analysis; the reported total is the
# real esearch count, not this.
_SAMPLE_SIZE = 60


class PubMedClient:
    def __init__(self):
        Entrez.email = "indicationscope@example.com"
        api_key = os.getenv("NCBI_API_KEY")
        if api_key:
            Entrez.api_key = api_key

    def fetch_publications(self, disease: str) -> dict:
        """Return {"total": int, "records": list[dict]} for a disease query."""
        total, pmids = self._search(disease)
        if not pmids:
            logger.info("PubMed: no results for %r", disease)
            return {"total": total, "records": []}

        records = self._fetch_records(pmids)
        logger.info(
            "PubMed fetch complete — disease=%r total=%d sampled=%d",
            disease, total, len(records),
        )
        return {"total": total, "records": records}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _search(self, query: str) -> tuple[int, list[str]]:
        """Return (true match count, sampled PMIDs)."""
        handle = Entrez.esearch(db="pubmed", term=query, retmax=_SAMPLE_SIZE)
        result = Entrez.read(handle)
        handle.close()
        try:
            total = int(result.get("Count", 0))
        except (TypeError, ValueError):
            total = 0
        return total, result.get("IdList", [])

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

            abstract_texts = art.get("Abstract", {}).get("AbstractText", [])
            abstract = " ".join(str(t) for t in abstract_texts)

            mesh_terms = [
                str(heading.get("DescriptorName", ""))
                for heading in (medline.get("MeshHeadingList") or [])
            ]

            journal_issue = art.get("Journal", {}).get("JournalIssue", {})
            pub_date = self._format_pub_date(journal_issue.get("PubDate", {}))

            results.append(
                {
                    "pmid": str(medline.get("PMID", "")),
                    "title": str(art.get("ArticleTitle", "")),
                    "abstract": abstract,
                    "mesh_terms": mesh_terms,
                    "mechanism_class": [],
                    "condition_normalized": [],
                    "pub_date": pub_date,
                    "publication_type": [str(p) for p in art.get("PublicationTypeList", [])],
                }
            )
        return results

    @staticmethod
    def _format_pub_date(pub_date: dict) -> str:
        year = pub_date.get("Year")
        if year:
            parts = [str(year)]
            if pub_date.get("Month"):
                parts.append(str(pub_date["Month"]))
            if pub_date.get("Day"):
                parts.append(str(pub_date["Day"]))
            return "-".join(parts)
        # Date-range records (e.g. "2023 Winter") use MedlineDate instead of Year/Month/Day.
        return str(pub_date.get("MedlineDate", ""))
