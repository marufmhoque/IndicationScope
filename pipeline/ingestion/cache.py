"""SQLite query-result cache keyed by SHA-256 of the serialised query dict."""

import hashlib
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parents[2] / "data" / "cache.db"


class QueryCache:
    def __init__(self, db_path: Path | None = None):
        self._path = db_path or _DEFAULT_DB
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def make_hash(query: dict) -> str:
        serialised = json.dumps(query, sort_keys=True)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def get(self, query_hash: str) -> dict | None:
        row = self._execute(
            "SELECT data FROM cache WHERE query_hash = ?", (query_hash,)
        ).fetchone()
        if row:
            logger.debug("Cache hit: %s…", query_hash[:8])
            return json.loads(row[0])
        return None

    def set(self, query_hash: str, data: dict) -> None:
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
        )

    def _execute(self, sql: str, params: tuple = (), *, commit: bool = False):
        conn = sqlite3.connect(self._path)
        try:
            cur = conn.execute(sql, params)
            if commit:
                conn.commit()
            return cur
        finally:
            conn.close()
