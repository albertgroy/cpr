from __future__ import annotations

import os
import re
from typing import Any

GLOBAL_FLAGS = {"--password", "--api-key", "--secret", "--token", "--key"}
PER_TOOL_FLAGS = {"mysql": {"-p"}, "ssh": {"-i"}, "scp": {"-i"}}
HASH_WHITELIST = [
    re.compile(r"^[0-9a-f]{40}$"),
    re.compile(r"^sha256:[0-9a-f]{64}$"),
    re.compile(r"^[0-9a-f]{7,12}$"),
    re.compile(r"^v?\d+(\.\d+)+(-\w+)*$"),
]
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$")
HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")
USER_AT_HOST = re.compile(r"^([^@]+)@(.+)$")
URL_USER = re.compile(r"^(https?://)([^/@]+)@(.+)$")
MAC_PATH = re.compile(r"^/Users/([^/]+)(/.*)?$")
LINUX_PATH = re.compile(r"^/home/([^/]+)(/.*)?$")
PRIVATE_PATHS = ("~/.ssh/", "~/.aws/", "~/.gnupg/")


def redact_args(tool: str, args: list[str], config: dict[str, Any] | None = None) -> list[str]:
    flags = _flags_for(tool, config or {})
    out: list[str] = []
    redact_next = False
    for arg in args:
        if redact_next:
            out.append("<REDACTED>")
            redact_next = False
            continue
        flag, sep, value = arg.partition("=")
        if sep and flag in flags:
            out.append(f"{flag}=<REDACTED>")
            continue
        if arg in flags:
            out.append(arg)
            redact_next = True
            continue
        out.append(redact_value(arg, keep_user=bool((config or {}).get("keep_user", False))))
    return out


def redact_value(value: str, keep_user: bool = False) -> str:
    if any(pattern.fullmatch(value) for pattern in HASH_WHITELIST):
        return value
    if value.startswith(PRIVATE_PATHS):
        return "<PRIVATE_PATH>"
    if BASE64_PATTERN.fullmatch(value) or (len(value) >= 40 and not HEX_PATTERN.fullmatch(value) and re.fullmatch(r"[A-Za-z0-9+/=]+", value)):
        return "<BLOB>"
    match = URL_USER.fullmatch(value)
    if match:
        return f"{match.group(1)}<USER>@{match.group(3)}"
    match = USER_AT_HOST.fullmatch(value)
    local_users = {os.environ.get("USER"), os.environ.get("LOGNAME"), "git"}
    if match and match.group(1) in local_users:
        return f"<USER>@{match.group(2)}"
    match = MAC_PATH.fullmatch(value)
    if match and not keep_user:
        return f"/Users/<USER>{match.group(2) or ''}"
    match = LINUX_PATH.fullmatch(value)
    if match and not keep_user:
        return f"/home/<USER>{match.group(2) or ''}"
    return value


def _flags_for(tool: str, config: dict[str, Any]) -> set[str]:
    flags = set(GLOBAL_FLAGS)
    flags.update(PER_TOOL_FLAGS.get(tool, set()))
    flags.update(config.get("extra_global_flags", []))
    extra_per_tool = config.get("extra_per_tool", {})
    if isinstance(extra_per_tool, dict):
        item = extra_per_tool.get(tool, {})
        if isinstance(item, dict):
            flags.update(item.get("redact_flags", []))
    return flags
