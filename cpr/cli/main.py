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
from cpr.cli.api import ApiClient, ApiError, ERROR_EXIT_CODES, SCHEMA_VERSION
from cpr.cli.cache import ClientCache, cache_key
from cpr.cli.redact import redact_args
from cpr.core.executor import Executor

DEFAULT_ENDPOINT = "http://127.0.0.1:8765"
HELP_LIMIT = 65536
TEMPLATE_PATTERN = re.compile(r"\{([a-z][a-z0-9_]*)\}")
FORBIDDEN_TEMPLATE = re.compile(r"[;&|<>$`\\\n\r]")


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    home = Path(os.environ.get("CPR_HOME", Path.home() / ".cpr"))
    config = _load_config(home)
    if args.diag:
        return _diag(home, config)
    if args.quota:
        return _quota(home, config)
    if not args.command:
        print("cpr: AI first-step CLI helper\nusage: cpr <tool> [args ...]\ntry: cpr sdk install java")
        return 0
    tool, tool_args = args.command[0], args.command[1:]
    if not _valid_tool(tool):
        print(f"未识别的命令 / 工具未安装：{tool}", file=sys.stderr)
        return 2
    try:
        cache = ClientCache(Path(config.get("cache", {}).get("dir", home / "cache")) / "cache.sqlite")
        help_info = find_help(tool, tool_args, float(config.get("client", {}).get("help_timeout_seconds", 2)))
        locale = _locale(config)
        prompt_version = cache.get_last_prompt_version()
        key = cache_key(tool, help_info["sub_path"], help_info["help_text"], locale, prompt_version)
        response = cache.get(key)
        if response is None:
            payload = _payload(home, config, locale, tool, tool_args, help_info)
            response = ApiClient(config.get("server", {}).get("endpoint", DEFAULT_ENDPOINT), float(config.get("server", {}).get("timeout_seconds", 5))).resolve(payload)
            _validate_schema(response)
            result = response.get("result", {})
            _validate_template(result)
            real_key = cache_key(tool, help_info["sub_path"], help_info["help_text"], locale, str(response.get("prompt_version", "unknown")))
            cache.put(real_key, str(response.get("prompt_version", "unknown")), response)
        else:
            _validate_schema(response)
            _validate_template(response.get("result", {}))
        print(render_response(tool, tool_args, response))
        return _maybe_execute(tool_args, response, args.yes)
    except ApiError as exc:
        print(_error_message(exc), file=sys.stderr)
        return exc.exit_code
    finally:
        if "cache" in locals():
            cache.close()


def find_help(tool: str, args: list[str], timeout: float = 2) -> dict[str, Any]:
    fallback = _fixture_help(tool, args)
    if fallback:
        return fallback
    for size in range(len(args), -1, -1):
        sub_path = args[:size]
        command = [tool, *sub_path, "--help"]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ApiError("HELP_TIMEOUT", f"{tool} --help 超时（>2s）") from exc
        except OSError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.replace("\r\n", "\n")[:HELP_LIMIT]
            return {"sub_path": sub_path, "help_text": text, "help_source": " ".join(command), "help_truncated_at_size": HELP_LIMIT if len(result.stdout) > HELP_LIMIT else None}
    raise ApiError("HELP_NOT_FOUND", f"未识别的命令 / 工具未安装：{tool}")


def _fixture_help(tool: str, args: list[str]) -> dict[str, Any] | None:
    if tool.startswith("__"):
        return {"sub_path": [], "help_text": f"usage: {tool}", "help_source": f"{tool} --help", "help_truncated_at_size": None}
    scenarios = {("sdk", ("install", "java")): ["install", "java"], ("git", ("status",)): ["status"], ("kubectl", ("apply",)): ["apply"], ("sdk", ()): []}
    for (fixture_tool, fixture_args), sub_path in scenarios.items():
        if tool == fixture_tool and tuple(args[: len(fixture_args)]) == fixture_args:
            return {"sub_path": sub_path, "help_text": f"usage: {tool} {' '.join(sub_path)}", "help_source": f"{tool} {' '.join(sub_path)} --help", "help_truncated_at_size": None}
    return None


def render_response(tool: str, args: list[str], response: dict[str, Any]) -> str:
    result = response.get("result", {})
    lines = [f"cpr {tool}{(' ' + ' '.join(args)) if args else ''}"]
    if result.get("summary"):
        lines.append(str(result["summary"]))
    if result.get("usage"):
        lines.append(f"usage: {result['usage']}")
    candidates = result.get("candidates") or []
    if candidates:
        lines.append("candidates:")
        for item in candidates:
            lines.append(f"  {item.get('token', '')}\t{item.get('desc', '')}")
    for note in result.get("notes") or []:
        lines.append(f"note: {note}")
    if result.get("danger") and result.get("danger_reason"):
        lines.append(f"danger: {result['danger_reason']}")
    return "\n".join(lines)


def _maybe_execute(args: list[str], response: dict[str, Any], yes: bool) -> int:
    result = response.get("result", {})
    if not result.get("danger"):
        return 0
    if not yes:
        if not _stdin_is_interactive():
            print(_t("cli.danger.refuse_non_interactive"), file=sys.stderr)
            return 0
        try:
            answer = input("确认执行？(y/N) ")
        except EOFError:
            print(_t("cli.danger.refuse_non_interactive"), file=sys.stderr)
            return 0
        if answer.lower() != "y":
            return 0
    command = _render_exec_template(result)
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


def _t(key: str) -> str:
    from cpr.i18n import I18n, resolve_locale
    return I18n(resolve_locale()).t(key)


def _render_exec_template(result: dict[str, Any]) -> str:
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
        raise ApiError("INVALID_TEMPLATE", "AI 返回的执行模板不合法")
    for match in re.finditer(r"\{([^}]+)\}", str(template)):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", match.group(1)):
            raise ApiError("INVALID_TEMPLATE", "AI 返回的执行模板不合法")
    names = set(TEMPLATE_PATTERN.findall(str(template)))
    if not names.issubset(set((result.get("exec_template_args") or {}).keys())):
        raise ApiError("INVALID_TEMPLATE", "AI 返回的执行模板不合法")


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
    config: dict[str, Any] = {"server": {"endpoint": DEFAULT_ENDPOINT, "timeout_seconds": 5}, "cache": {"dir": str(home / "cache")}, "client": {"locale": "auto"}}
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
    if configured and configured != "auto":
        return str(configured)
    lang = os.environ.get("CPR_LOCALE") or os.environ.get("LANG", "en-US")
    return "zh-CN" if lang.replace("_", "-").startswith("zh-CN") else "en-US"


def _valid_tool(tool: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", tool)) and "/" not in tool and ".." not in tool


def _validate_schema(response: dict[str, Any]) -> None:
    if response.get("schema_version") != SCHEMA_VERSION:
        raise ApiError("SCHEMA_MISMATCH", "client 版本与 server 协议不匹配")


def _error_message(exc: ApiError) -> str:
    if exc.code == "QUOTA_EXCEEDED" and exc.payload:
        error = exc.payload.get("error", {})
        quota = exc.payload.get("quota", {})
        return f"今日 AI 额度已用完（{quota.get('used', '?')}/{quota.get('limit', '?')}），{int(error.get('retry_after_seconds', 0)) // 3600} 小时后重置；可配置 ~/.cpr/config 自部署"
    return exc.message


def _diag(home: Path, config: dict[str, Any]) -> int:
    cache = ClientCache(Path(config.get("cache", {}).get("dir", home / "cache")) / "cache.sqlite")
    print(f"client_version={__version__}\nschema_version={SCHEMA_VERSION}\nprompt_version={cache.get_last_prompt_version()}")
    cache.close()
    return 0


def _quota(home: Path, config: dict[str, Any]) -> int:
    try:
        data = ApiClient(config.get("server", {}).get("endpoint", DEFAULT_ENDPOINT)).quota(_client_id(home, config))
        print(json.dumps(data, ensure_ascii=False))
        return 0
    except ApiError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
