from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1"
ERROR_EXIT_CODES = {
    "HELP_NOT_FOUND": 2,
    "HELP_TIMEOUT": 2,
    "NETWORK_UNREACHABLE": 3,
    "LLM_TIMEOUT": 3,
    "SERVER_ERROR": 3,
    "QUOTA_EXCEEDED": 4,
    "BAD_REQUEST": 5,
    "INVALID_CLIENT": 5,
    "INVALID_TEMPLATE": 5,
    "SCHEMA_MISMATCH": 5,
    "LLM_PARSE_FAILED": 5,
}


@dataclass(frozen=True)
class ApiError(Exception):
    code: str
    message: str
    payload: dict[str, Any] | None = None

    @property
    def exit_code(self) -> int:
        return ERROR_EXIT_CODES.get(self.code, 5)


class ApiClient:
    def __init__(self, endpoint: str, timeout_seconds: float = 5) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def resolve(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(f"{self.endpoint}/resolve", data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            data = _load_error(exc)
            error = data.get("error", {}) if isinstance(data, dict) else {}
            raise ApiError(str(error.get("code", "SERVER_ERROR")), str(error.get("message", exc)), data) from exc
        except TimeoutError as exc:
            raise ApiError("LLM_TIMEOUT", "AI 解析超时") from exc
        except URLError as exc:
            reason = str(exc.reason)
            code = "LLM_TIMEOUT" if "timed out" in reason.lower() else "NETWORK_UNREACHABLE"
            raise ApiError(code, "server 不可达，请检查 ~/.cpr/config") from exc

    def quota(self, client_id: str) -> dict[str, Any]:
        try:
            with urlopen(f"{self.endpoint}/quota?client_id={client_id}", timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ApiError("NETWORK_UNREACHABLE", "server 不可达，请检查 ~/.cpr/config") from exc


def _load_error(exc: HTTPError) -> dict[str, Any]:
    try:
        return json.loads(exc.read().decode("utf-8"))
    except Exception:
        return {"error": {"code": "SERVER_ERROR", "message": str(exc)}}
