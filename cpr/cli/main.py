from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import uuid

import yaml

from cpr import __version__
from cpr.cli.api import ApiClient, ApiError, SCHEMA_VERSION
from cpr.cli.cache import ClientCache, cache_key
from cpr.cli.redact import redact_args
from cpr.cli.render import confirm_danger, render_error_payload, render_no_args, render_quota_status, render_response
from cpr.core.executor import Executor
from cpr.i18n import I18n, resolve_locale

HELP_LIMIT = 65536
TEMPLATE_PATTERN = re.compile(r"\{([a-z][a-z0-9_]*)\}")
FORBIDDEN_TEMPLATE = re.compile(r"[;&|<>$`\\\n\r]")
_CONFIRMED_DANGER: set[tuple[str, str]] = set()


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    home = Path(os.environ.get("CPR_HOME", Path.home() / ".cpr"))
    config = _load_config(home)
    locale = _locale(config)
    if args.diag:
        return _diag(home, config)
    if args.quota:
        return _quota(home, config, locale)
    if not args.command:
        print(render_no_args(locale=locale))
        return 0
    tool, tool_args = args.command[0], args.command[1:]
    help_timeout = float(config.get("client", {}).get("help_timeout_seconds", 2))
    cache: ClientCache | None = None
    try:
        if not _valid_tool(tool):
            raise ApiError("HELP_NOT_FOUND", "")
        cache = ClientCache(Path(config.get("cache", {}).get("dir", home / "cache")) / "cache.sqlite")
        help_info = find_help(tool, tool_args, help_timeout)
        prompt_version = cache.get_last_prompt_version()
        key = cache_key(tool, help_info["sub_path"], help_info["help_text"], locale, prompt_version)
        response = cache.get(key)
        if response is None:
            payload = _payload(home, config, locale, tool, tool_args, help_info)
            response = ApiClient(config.get("server", {}).get("endpoint"), float(config.get("server", {}).get("timeout_seconds", 5))).resolve(payload)
            _validate_schema(response)
            result = response.get("result", {})
            _validate_template(result)
            real_key = cache_key(tool, help_info["sub_path"], help_info["help_text"], locale, str(response.get("prompt_version", "unknown")))
            cache.put(real_key, str(response.get("prompt_version", "unknown")), response)
        else:
            _validate_schema(response)
            _validate_template(response.get("result", {}))
        print(render_response(tool, tool_args, response, locale=locale))
        return _maybe_execute(tool, response, args.yes, _confirm_mode(config), locale)
    except ApiError as exc:
        print(_render_api_error(exc, locale=locale, tool=tool, timeout=help_timeout), file=sys.stderr)
        return exc.exit_code
    finally:
        if cache is not None:
            cache.close()


def find_help(tool: str, args: list[str], timeout: float = 2) -> dict[str, Any]:
    for size in range(len(args), -1, -1):
        sub_path = args[:size]
        command = [tool, *sub_path, "--help"]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ApiError("HELP_TIMEOUT", "") from exc
        except OSError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.replace("\r\n", "\n")[:HELP_LIMIT]
            return {"sub_path": sub_path, "help_text": text, "help_source": " ".join(command), "help_truncated_at_size": HELP_LIMIT if len(result.stdout) > HELP_LIMIT else None}
    raise ApiError("HELP_NOT_FOUND", "")


def _maybe_execute(tool: str, response: dict[str, Any], yes: bool, confirm_mode: str, locale: str, confirmed: set[tuple[str, str]] | None = None) -> int:
    result = response.get("result", {})
    if not result.get("danger"):
        return 0
    command = _render_exec_command(result)
    confirmed = _CONFIRMED_DANGER if confirmed is None else confirmed
    key = (tool, str(result.get("exec_template", "")))
    skip_prompt = yes or confirm_mode == "never" or (confirm_mode == "once" and key in confirmed)
    if not skip_prompt:
        if not _stdin_is_interactive():
            print(_t("cli.danger.refuse_non_interactive", locale), file=sys.stderr)
            return 0

        def input_func(prompt: str) -> str:
            try:
                return input(prompt)
            except EOFError:
                print(_t("cli.danger.refuse_non_interactive", locale), file=sys.stderr)
                raise

        if not confirm_danger(locale=locale, input_func=input_func):
            return 0
        if confirm_mode == "once":
            confirmed.add(key)
    executed = Executor().run_sync(command, result.get("exec_shell_mode", "direct"))
    if executed.stdout:
        print(executed.stdout, end="")
    if executed.stderr:
        print(executed.stderr, file=sys.stderr, end="")
    return executed.exit_code


def _stdin_is_interactive() -> bool:
    isatty = getattr(sys.stdin, "isatty", None)
    try:
        return bool(isatty()) if callable(isatty) else False
    except (ValueError, OSError):
        return False


def _t(key: str, locale: str | None = None) -> str:
    return I18n(locale or resolve_locale()).t(key)


def _render_exec_command(result: dict[str, Any]) -> str:
    template = str(result.get("exec_template", ""))
    candidates = result.get("candidates") or []
    values = {item.get("kind"): item.get("token") for item in candidates if item.get("token")}
    for name, spec in (result.get("exec_template_args") or {}).items():
        if spec.get("from") == "candidates":
            value = values.get(spec.get("kind"))
            if value:
                template = template.replace("{" + name + "}", str(value))
    return template


def _validate_template(result: dict[str, Any]) -> None:
    template = result.get("exec_template")
    if not template:
        return
    if FORBIDDEN_TEMPLATE.search(str(template)) or any(ord(ch) < 32 or ord(ch) > 126 for ch in str(template)):
        raise ApiError("INVALID_TEMPLATE", "")
    for match in re.finditer(r"\{([^}]+)\}", str(template)):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", match.group(1)):
            raise ApiError("INVALID_TEMPLATE", "")
    names = set(TEMPLATE_PATTERN.findall(str(template)))
    if not names.issubset(set((result.get("exec_template_args") or {}).keys())):
        raise ApiError("INVALID_TEMPLATE", "")


def _payload(home: Path, config: dict[str, Any], locale: str, tool: str, args: list[str], help_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "client_id": _client_id(home, config),
        "client_version": __version__,
        "locale": locale,
        "tool": tool,
        "args": redact_args(tool, args, config.get("redact", {})),
        "sub_path": help_info["sub_path"],
        "help_text": help_info["help_text"],
        "help_source": help_info["help_source"],
        "help_truncated_at_size": help_info["help_truncated_at_size"],
    }


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cpr")
    parser.add_argument("--diag", action="store_true")
    parser.add_argument("--quota", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("command", nargs="*")
    return parser.parse_args(argv)


def _load_config(home: Path) -> dict[str, Any]:
    path = home / "config"
    config: dict[str, Any] = {"server": {"timeout_seconds": 5}, "cache": {"dir": str(home / "cache")}, "client": {"locale": "auto", "confirm_danger": "always"}}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key].update(value)
                else:
                    config[key] = value
    return config


def _client_id(home: Path, config: dict[str, Any]) -> str:
    existing = config.get("client", {}).get("id")
    if existing:
        return str(existing)
    home.mkdir(parents=True, exist_ok=True)
    path = home / "config"
    client_id = str(uuid.uuid4())
    data = config | {"client": {**config.get("client", {}), "id": client_id}}
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return client_id


def _locale(config: dict[str, Any]) -> str:
    configured = config.get("client", {}).get("locale")
    return resolve_locale(config_locale=str(configured) if configured else None)


def _confirm_mode(config: dict[str, Any]) -> str:
    value = str(config.get("client", {}).get("confirm_danger", "always"))
    return value if value in {"always", "once", "never"} else "always"


def _valid_tool(tool: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", tool)) and "/" not in tool and ".." not in tool


def _validate_schema(response: dict[str, Any]) -> None:
    if response.get("schema_version") != SCHEMA_VERSION:
        raise ApiError("SCHEMA_MISMATCH", "")


def _render_api_error(exc: ApiError, *, locale: str, tool: str | None = None, timeout: float | None = None) -> str:
    error = {"code": exc.code, "message": exc.message}
    response = exc.payload if isinstance(exc.payload, dict) else None
    server_version = None
    if response:
        server_version = response.get("server_version") or response.get("schema_version")
    return render_error_payload(error, response=response, tool=tool, timeout=timeout, client_version=__version__, server_version=server_version, locale=locale)


def _diag(home: Path, config: dict[str, Any]) -> int:
    cache = ClientCache(Path(config.get("cache", {}).get("dir", home / "cache")) / "cache.sqlite")
    print(f"client_version={__version__}\nschema_version={SCHEMA_VERSION}\nprompt_version={cache.get_last_prompt_version()}")
    cache.close()
    return 0


def _quota(home: Path, config: dict[str, Any], locale: str) -> int:
    try:
        data = ApiClient(config.get("server", {}).get("endpoint")).quota(_client_id(home, config))
        print(render_quota_status(data, locale=locale))
        return 0
    except ApiError as exc:
        print(_render_api_error(exc, locale=locale, timeout=float(config.get("server", {}).get("timeout_seconds", 5))), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
