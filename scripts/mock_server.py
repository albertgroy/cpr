#!/usr/bin/env python3
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "server"
ERRORS = {
    "__quota": "quota_exceeded",
    "__timeout": "llm_timeout",
    "__server_error": "server_error",
    "__invalid_template": "invalid_template",
    "__schema_mismatch": "schema_mismatch",
}
STATUS = {
    "quota_exceeded": 429,
    "llm_timeout": 504,
    "server_error": 500,
    "invalid_template": 200,
    "schema_mismatch": 426,
}
SCENARIOS = {
    ("sdk", ("install", "java")): "sdk_install_java",
    ("git", ("status",)): "git_status",
    ("kubectl", ("apply",)): "kubectl_apply",
    ("sdk", ()): "sdk_root",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {"status": "ok", "server_version": "0.1.0"})
        elif path == "/quota":
            self._json(200, {"used": 1, "limit": 50, "reset_at": "2026-06-20T00:00:00Z"})
        else:
            self._json(404, {"schema_version": "1", "error": {"code": "SERVER_ERROR", "message": "not found"}})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/resolve":
            self._json(404, {"schema_version": "1", "error": {"code": "SERVER_ERROR", "message": "not found"}})
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length).decode("utf-8"))
        tool = request.get("tool")
        if tool in ERRORS:
            name = ERRORS[tool]
            self._json(STATUS[name], _read(FIXTURES / "errors" / name / "response.json"))
            return
        name = SCENARIOS.get((tool, tuple(request.get("sub_path", []))))
        if name:
            self._json(200, _read(FIXTURES / "scenarios" / name / "response.json"))
            return
        self._json(502, {"schema_version": "1", "error": {"code": "LLM_PARSE_FAILED", "message": "no fixture"}})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
