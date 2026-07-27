"""Disease-name normalisation using a static MeSH/Orphanet crosswalk CSV.

Falls back to LLM extraction (claude-haiku) for terms not found in the table.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CROSSWALK_PATH = Path(__file__).parents[2] / "data" / "ontology_crosswalk.csv"


class OntologyCrosswalk:
    def __init__(self):
        # TODO: load crosswalk CSV into a lookup dict keyed by lowercase raw term
        self._table: dict[str, str] = {}
        self._load()

    def normalise(self, raw_term: str) -> str:
        """Return a canonical disease name; falls back to the raw term if unmapped."""
        key = raw_term.strip().lower()
        if key in self._table:
            return self._table[key]
        # TODO: fuzzy match against crosswalk entries
        # TODO: LLM fallback via EXTRACTION_MODEL for unrecognised terms
        logger.debug("Ontology miss: %r — returning raw term", raw_term)
        return raw_term

    def _load(self) -> None:
        if not _CROSSWALK_PATH.exists():
            logger.warning("Crosswalk CSV not found at %s", _CROSSWALK_PATH)
            return
        # TODO: parse CSV; columns expected: raw_term, canonical_name, mesh_id, orphanet_id
        import csv

        with _CROSSWALK_PATH.open() as f:
            for row in csv.DictReader(f):
                key = row.get("raw_term", "").strip().lower()
                value = row.get("canonical_name", "").strip()
                if key and value:
                    self._table[key] = value
        logger.info("Loaded %d ontology entries", len(self._table))
