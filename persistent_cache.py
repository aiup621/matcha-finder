import os
import sqlite3
import time
from datetime import date
from typing import Optional

class PersistentCache:
    TTL_NEG = int(os.getenv("PERSISTENT_CACHE_TTL_NEG", "7")) * 86400

    def __init__(self, path: str | None = None):
        if path is None:
            today = date.today().strftime("%Y%m%d")
            path = f".cache/crawler-{today}.sqlite"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path)
        with self.conn:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS visits(
                    url TEXT PRIMARY KEY,
                    status TEXT,
                    reason TEXT,
                    ts INTEGER
                )"""
            )
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS adds(
                    url TEXT PRIMARY KEY,
                    name TEXT,
                    ts INTEGER
                )"""
            )

    def seen(self, url: str) -> Optional[str]:
        cur = self.conn.execute("SELECT status, ts FROM visits WHERE url=?", (url,))
        row = cur.fetchone()
        if not row:
            return None
        status, ts = row
        if status != "add" and time.time() - ts > self.TTL_NEG:
            return None
        return status

    def record(self, url: str, status: str, reason: str = "") -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO visits(url,status,reason,ts) VALUES(?,?,?,?)",
                (url, status, reason, int(time.time())),
            )

    def record_add(self, url: str, name: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO adds(url,name,ts) VALUES(?,?,?)",
                (url, name, int(time.time())),
            )

__all__ = ["PersistentCache"]
