from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import time
from typing import Protocol

from cpr.core.executor import Executor
from cpr.core.model import CommandNode, CommandTree
from cpr.core.session import CommandSession


@dataclass(frozen=True)
class Candidate:
    token: str
    label: str
    desc: str = ""
    source: str = "static"


@dataclass(frozen=True)
class CandidateError:
    code: str
    message: str


@dataclass(frozen=True)
class CandidateResult:
    candidates: tuple[Candidate, ...]
    error: CandidateError | None = None


class CandidateProvider(Protocol):
    async def provide(self, node: CommandNode | None, session: CommandSession) -> CandidateResult:
        ...


class StaticCandidateProvider:
    def __init__(self, tree: CommandTree, locale: str = "zh-CN") -> None:
        self.tree = tree
        self.locale = locale

    async def provide(self, node: CommandNode | None, session: CommandSession) -> CandidateResult:
        children = node.children if node else tuple(self.tree.get(node_id) for node_id in self.tree.root_ids)
        candidates = tuple(
            Candidate(token=child.token, label=child.title.get(self.locale) or child.title.get("en-US") or child.id, desc=child.desc.get(self.locale) or child.desc.get("en-US") or "")
            for child in children
        )
        return CandidateResult(candidates=candidates)


class DynamicCandidateProvider:
    def __init__(self, executor: Executor, ttl_seconds: int = 60) -> None:
        self.executor = executor
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, CandidateResult]] = {}

    async def provide(self, node: CommandNode | None, session: CommandSession) -> CandidateResult:
        if not node or not node.param:
            return CandidateResult(candidates=())
        source = node.param.source
        cached = self._cache.get(source)
        now = time.monotonic()
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        try:
            if source == "sdk.candidates.java.identifiers":
                result = await self._java_identifiers()
            elif source == "sdk.installed.java.versions":
                result = await self._installed_java_versions()
            else:
                result = CandidateResult(candidates=(), error=CandidateError("unsupported_source", source))
        except Exception as exc:
            result = CandidateResult(candidates=(), error=CandidateError("parse_failed", str(exc)))
        self._cache[source] = (now, result)
        return result

    def invalidate_after_command(self, command: str, ok: bool) -> None:
        if not ok:
            return
        tokens = command.split()
        if len(tokens) >= 3 and tokens[0] == "sdk" and tokens[1] in {"install", "use", "default"}:
            self.invalidate("sdk.installed.java.versions")
            self.invalidate("sdk.candidates.java.identifiers")

    def invalidate(self, source: str) -> None:
        self._cache.pop(source, None)

    async def _java_identifiers(self) -> CandidateResult:
        result = await self.executor.run("sdk list java", "bash-lc-source")
        if not result.ok:
            return CandidateResult(candidates=(), error=CandidateError("command_failed", result.stderr or result.stdout))
        identifiers = _parse_sdk_java_identifiers(result.stdout)
        return CandidateResult(candidates=tuple(Candidate(token=value, label=value, source="dynamic") for value in identifiers))

    async def _installed_java_versions(self) -> CandidateResult:
        result = await asyncio.to_thread(self.executor.list_installed_java_versions)
        return CandidateResult(candidates=tuple(Candidate(token=value, label=value, source="dynamic") for value in result))


def _parse_sdk_java_identifiers(text: str) -> list[str]:
    identifiers: list[str] = []
    for line in text.splitlines():
        if "|" not in line or line.lstrip().startswith("="):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 6 or parts[0].lower() in {"vendor", ""}:
            continue
        identifier = parts[-1]
        if re.fullmatch(r"[0-9][A-Za-z0-9._+-]*", identifier):
            identifiers.append(identifier)
    return identifiers
