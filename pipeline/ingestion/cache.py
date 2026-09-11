"""SQLite query-result cache keyed by SHA-256 of the serialised query dict.

Every operation is best-effort. A cache is an optimisation, so a cache failure
must never break a request — an earlier version constructed this at module import
and took the whole API down with a 500 when the filesystem was read-only.
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


class QueryCache:
    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _default_db_path()
        self._enabled = True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._init()
        except (OSError, sqlite3.Error) as exc:
            self._enabled = False
            logger.warning(
                "Query cache disabled (%s: %s) — continuing without caching",
                type(exc).__name__, exc,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _init(self) -> None:
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                query_hash TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """,
            commit=True,
            raise_on_error=True,
        )

    def _execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        commit: bool = False,
        fetch: bool = False,
        raise_on_error: bool = False,
    ):
        """Run SQL against the cache DB.

        Rows must be fetched before the connection closes, so `fetch=True`
        returns the first row rather than the cursor.
        """
        conn = None
        try:
            conn = sqlite3.connect(self._path)
            cur = conn.execute(sql, params)
            row = cur.fetchone() if fetch else None
            if commit:
                conn.commit()
            return row
        except (OSError, sqlite3.Error) as exc:
            if raise_on_error:
                raise
            logger.warning("Cache operation failed (%s) — ignoring", type(exc).__name__)
            self._enabled = False
            return None
        finally:
            if conn is not None:
                conn.close()
