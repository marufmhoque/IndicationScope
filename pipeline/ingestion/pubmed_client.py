"""PubMed client using the NCBI E-utilities HTTP API directly.

Deliberately not Biopython: its Entrez parser resolves DTDs against an on-disk
cache, which fails on a read-only serverless filesystem — PubMed returned zero
results in production while working locally. Plain httpx plus the stdlib XML
parser has no filesystem dependency, and drops a heavy package from the
deployment bundle.

esearch reports the true match count while honouring a small retmax, so the
headline number stays accurate while only a sample is fetched.
"""

import logging
import os
import xml.etree.ElementTree as ET

import httpx

from config import NCBI_BASE

logger = logging.getLogger(__name__)

# Records actually fetched for mechanism analysis; the reported total is the
# real esearch count, not this.
_SAMPLE_SIZE = 200
_TIMEOUT = 20

# Authors kept per article. Consortium papers can list hundreds, which would
# dominate the cached payload for no analytical gain — the leading names are
# what the researcher ranking needs.
_MAX_AUTHORS = 10

# NCBI asks callers to identify themselves so it can contact you about misuse.
_TOOL = "indicationscope"
_EMAIL = "indicationscope@example.com"


class PubMedClient:
    def __init__(self, base_url: str = NCBI_BASE):
        self.base_url = base_url.rstrip("/")
        self.api_key = os.getenv("NCBI_API_KEY")

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

    def _params(self, **extra) -> dict:
        params = {"db": "pubmed", "tool": _TOOL, "email": _EMAIL, **extra}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _search(self, query: str) -> tuple[int, list[str]]:
        """Return (true match count, sampled PMIDs)."""
        resp = httpx.get(
            f"{self.base_url}/esearch.fcgi",
            params=self._params(term=query, retmax=_SAMPLE_SIZE, retmode="json"),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json().get("esearchresult", {})
        try:
            total = int(result.get("count", 0))
        except (TypeError, ValueError):
            total = 0
        return total, result.get("idlist", [])

    def _fetch_records(self, pmids: list[str]) -> list[dict]:
        if not pmids:
            return []

        resp = httpx.get(
            f"{self.base_url}/efetch.fcgi",
            params=self._params(id=",".join(pmids), retmode="xml"),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        results: list[dict] = []
        for article in root.findall(".//PubmedArticle"):
            journal_issue = article.find(".//Article/Journal/JournalIssue")
            results.append(
                {
                    "pmid": article.findtext(".//MedlineCitation/PMID", default=""),
                    "title": self._text(article.find(".//Article/ArticleTitle")),
                    "abstract": " ".join(
                        self._text(seg)
                        for seg in article.findall(".//Article/Abstract/AbstractText")
                    ).strip(),
                    "mesh_terms": [
                        self._text(d)
                        for d in article.findall(
                            ".//MeshHeadingList/MeshHeading/DescriptorName"
                        )
                    ],
                    "mechanism_class": [],
                    "condition_normalized": [],
                    "pub_date": self._format_pub_date(
                        journal_issue.find("PubDate") if journal_issue is not None else None
                    ),
                    "publication_type": [
                        self._text(p)
                        for p in article.findall(".//PublicationTypeList/PublicationType")
                    ],
                    "authors": self._authors(article),
                }
            )
        return results

    @classmethod
    def _authors(cls, article) -> list[dict]:
        """Extract leading authors as {name, affiliation}.

        Entries without a LastName (collective/consortium authors) are skipped —
        they carry no individual attribution.
        """
        authors: list[dict] = []
        for person in article.findall(".//AuthorList/Author")[:_MAX_AUTHORS]:
            last = person.findtext("LastName")
            if not last:
                continue
            fore = person.findtext("ForeName") or person.findtext("Initials") or ""
            authors.append(
                {
                    "name": f"{fore} {last}".strip(),
                    "affiliation": cls._text(person.find("AffiliationInfo/Affiliation")),
                }
            )
        return authors

    @staticmethod
    def _text(element) -> str:
        """Flatten an element's text, including any nested inline markup."""
        if element is None:
            return ""
        return "".join(element.itertext()).strip()

    @staticmethod
    def _format_pub_date(pub_date) -> str:
        if pub_date is None:
            return ""
        year = pub_date.findtext("Year")
        if year:
            parts = [year]
            for field in ("Month", "Day"):
                value = pub_date.findtext(field)
                if value:
                    parts.append(value)
            return "-".join(parts)
        # Date-range records (e.g. "2023 Winter") use MedlineDate instead.
        return pub_date.findtext("MedlineDate") or ""
