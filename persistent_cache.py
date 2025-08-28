import os
import sqlite3
import time
from typing import Optional

class PersistentCache:
    def __init__(self, path: str = ".cache/crawler.sqlite"):
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
        cur = self.conn.execute("SELECT status FROM visits WHERE url=?", (url,))
        row = cur.fetchone()
        return row[0] if row else None

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
