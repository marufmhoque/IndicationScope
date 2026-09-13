"""SQLite caches backing the pipeline.

Every operation is best-effort. A cache is an optimisation, so a cache failure
must never break a request — an earlier version constructed this at module import
and took the whole API down with a 500 when the filesystem was read-only.

Three caches share one database file:

- QueryCache: a whole ingestion result, keyed by the query. Short-lived value.
- MechanismCache: entity -> mechanism class, keyed by the entity itself rather
  than the query. Aflibercept is a VEGF antagonist regardless of which disease
  was searched, so those entries are reusable across searches and never need
  invalidating.
- BriefingCache: the executive briefing, keyed by disease. The most expensive
  single call in the app, and identical for repeat views of the same disease.
"""

import hashlib
import json
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_db_path() -> Path:
    """Serverless filesystems are read-only apart from /tmp.

    On Vercel that /tmp is per-instance and ephemeral, so the cache only ever
    helps a warm instance — which is fine, it's purely an optimisation.
    """
    if os.getenv("VERCEL"):
        return Path("/tmp/cache.db")
    return Path(__file__).parents[2] / "data" / "cache.db"


class _SqliteCache:
    """Shared connection handling. Any failure disables the cache, never raises."""

    _TABLE_DDL = ""

    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _default_db_path()
        self._enabled = True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._execute(self._TABLE_DDL, commit=True, raise_on_error=True)
        except (OSError, sqlite3.Error) as exc:
            self._enabled = False
            logger.warning(
                "%s disabled (%s: %s) — continuing without caching",
                type(self).__name__, type(exc).__name__, exc,
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        commit: bool = False,
        fetch: bool = False,
        fetch_all: bool = False,
        many: list | None = None,
        raise_on_error: bool = False,
    ):
        """Run SQL against the cache DB.

        Rows must be fetched before the connection closes, so `fetch`/`fetch_all`
        return rows rather than the cursor.
        """
        conn = None
        try:
            conn = sqlite3.connect(self._path)
            if many is not None:
                conn.executemany(sql, many)
                result = None
            else:
                cur = conn.execute(sql, params)
                result = cur.fetchall() if fetch_all else (cur.fetchone() if fetch else None)
            if commit:
                conn.commit()
            return result
        except (OSError, sqlite3.Error) as exc:
            if raise_on_error:
                raise
            logger.warning("Cache operation failed (%s) — ignoring", type(exc).__name__)
            self._enabled = False
            return None
        finally:
            if conn is not None:
                conn.close()


class QueryCache(_SqliteCache):
    """Caches a whole ingestion result, keyed by the query."""

    _TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS cache (
            query_hash TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """

    @staticmethod
    def make_hash(query: dict) -> str:
        serialised = json.dumps(query, sort_keys=True)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def get(self, query_hash: str) -> dict | None:
        if not self._enabled:
            return None
        row = self._execute(
            "SELECT data FROM cache WHERE query_hash = ?", (query_hash,), fetch=True
        )
        if row:
            logger.debug("Cache hit: %s…", query_hash[:8])
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Discarding corrupt cache entry %s…", query_hash[:8])
                return None
        return None

    def set(self, query_hash: str, data: dict) -> None:
        if not self._enabled:
            return
        self._execute(
            "INSERT OR REPLACE INTO cache (query_hash, data) VALUES (?, ?)",
            (query_hash, json.dumps(data)),
            commit=True,
        )
        logger.debug("Cache set: %s…", query_hash[:8])


class MechanismCache(_SqliteCache):
    """Caches entity -> mechanism classification across searches.

    Keyed by a stable entity id (a normalised drug name, or a PMID), not by the
    query that surfaced it, so an expensive classification is paid for once and
    reused by every later search touching the same entity.
    """

    _TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS mechanism_cache (
            entity_key TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """

    def get_many(self, keys: list[str]) -> dict[str, dict]:
        """Return the subset of keys already classified."""
        if not self._enabled or not keys:
            return {}

        placeholders = ",".join("?" * len(keys))
        rows = self._execute(
            f"SELECT entity_key, data FROM mechanism_cache WHERE entity_key IN ({placeholders})",
            tuple(keys),
            fetch_all=True,
        )
        if not rows:
            return {}

        hits: dict[str, dict] = {}
        for key, payload in rows:
            try:
                hits[key] = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
        if hits:
            logger.info("Mechanism cache: %d/%d already classified", len(hits), len(keys))
        return hits

    def set_many(self, results: dict[str, dict]) -> None:
        if not self._enabled or not results:
            return
        self._execute(
            "INSERT OR REPLACE INTO mechanism_cache (entity_key, data) VALUES (?, ?)",
            commit=True,
            many=[(key, json.dumps(value)) for key, value in results.items()],
        )
        logger.debug("Mechanism cache: stored %d entries", len(results))


class BriefingCache(_SqliteCache):
    """Caches the executive briefing, keyed by disease.

    The briefing is the largest single model call in the app and is the same for
    every view of a disease, so re-deriving it per page load is pure waste.
    """

    _TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS briefing_cache_v2 (
            disease    TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """

    def get(self, disease: str) -> dict | None:
        if not self._enabled or not disease:
            return None
        row = self._execute(
            "SELECT data FROM briefing_cache_v2 WHERE disease = ?",
            (disease.strip().lower(),),
            fetch=True,
        )
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None

    def set(self, disease: str, data: dict) -> None:
        if not self._enabled or not disease:
            return
        self._execute(
            "INSERT OR REPLACE INTO briefing_cache_v2 (disease, data) VALUES (?, ?)",
            (disease.strip().lower(), json.dumps(data)),
            commit=True,
        )
