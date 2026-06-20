from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any

SCHEMA_VERSION = "1"


def normalize_sub_path(sub_path: list[str]) -> str:
    return "/".join(part.strip().lower() for part in sub_path if part.strip())


def normalize_help_text(help_text: str) -> bytes:
    return help_text.replace("\r\n", "\n").rstrip().encode("utf-8")


def cache_key(tool: str, sub_path: list[str], help_text: str, locale: str, prompt_version: str, schema_version: str = SCHEMA_VERSION) -> str:
    h = hashlib.sha256()
    prefix = f"{schema_version}\n{prompt_version}\n{tool}\n{normalize_sub_path(sub_path)}\n{locale}\n"
    h.update(prefix.encode("utf-8"))
    h.update(normalize_help_text(help_text))
    return h.hexdigest()


class ClientCache:
    def __init__(self, path: Path, schema_version: str = SCHEMA_VERSION, max_entries: int = 1000) -> None:
        self.path = path
        self.schema_version = schema_version
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self._init()

    def close(self) -> None:
        self.conn.close()

    def get_last_prompt_version(self) -> str:
        row = self.conn.execute("SELECT prompt_version FROM entries WHERE schema_version = ? ORDER BY created_at DESC LIMIT 1", (self.schema_version,)).fetchone()
        return str(row[0]) if row else "unknown"

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT response_json, hit_count FROM entries WHERE key = ? AND schema_version = ?", (key, self.schema_version)).fetchone()
        if not row:
            return None
        self.conn.execute("UPDATE entries SET hit_count = ? WHERE key = ?", (int(row[1]) + 1, key))
        self.conn.commit()
        return json.loads(row[0])

    def put(self, key: str, prompt_version: str, response: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO entries(key, schema_version, prompt_version, response_json, created_at, hit_count) VALUES (?, ?, ?, ?, ?, COALESCE((SELECT hit_count FROM entries WHERE key = ?), 0))",
            (key, self.schema_version, prompt_version, json.dumps(response, ensure_ascii=False, sort_keys=True), int(time.time()), key),
        )
        self._evict()
        self.conn.commit()

    def _init(self) -> None:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS entries (key TEXT PRIMARY KEY, schema_version TEXT NOT NULL, prompt_version TEXT NOT NULL, response_json TEXT NOT NULL, created_at INTEGER NOT NULL, hit_count INTEGER NOT NULL DEFAULT 0)"
        )
        self.conn.execute("DELETE FROM entries WHERE schema_version != ?", (self.schema_version,))
        self.conn.commit()

    def _evict(self) -> None:
        self.conn.execute(
            "DELETE FROM entries WHERE key IN (SELECT key FROM entries ORDER BY (created_at + hit_count) ASC LIMIT MAX((SELECT COUNT(*) FROM entries) - ?, 0))",
            (self.max_entries,),
        )
