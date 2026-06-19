from dataclasses import dataclass
from pathlib import Path

import pytest

from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.candidates import DynamicCandidateProvider, StaticCandidateProvider, _parse_sdk_java_identifiers
from cpr.core.executor import ExecutionResult
from cpr.core.model import load_command_tree
from cpr.core.session import CommandSession


@pytest.mark.asyncio
async def test_static_candidates_from_children():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    provider = StaticCandidateProvider(tree)
    result = await provider.provide(tree.get("sdk"), session)
    assert [candidate.token for candidate in result.candidates] == ["list", "install", "use", "default", "current"]
    assert result.candidates[0].source == "static"


def test_parse_sdk_java_identifiers():
    text = "Vendor | Use | Version | Dist | Status | Identifier\nTemurin |     | 17.0.10 | tem |      | 17.0.10-tem\nZulu |     | 21.0.2 | zulu |      | 21.0.2-zulu"
    assert _parse_sdk_java_identifiers(text) == ["17.0.10-tem", "21.0.2-zulu"]


@dataclass
class FakeExecutor:
    stdout: str
    ok: bool = True
    calls: int = 0

    async def run(self, command, shell_mode):
        self.calls += 1
        return ExecutionResult(self.ok, self.stdout, "boom" if not self.ok else "", 0 if self.ok else 1, 1)

    def list_installed_java_versions(self):
        return ["17.0.10-tem"]


@pytest.mark.asyncio
async def test_dynamic_identifier_candidates_cache_and_invalidate():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    executor = FakeExecutor("Temurin |     | 17.0.10 | tem |      | 17.0.10-tem")
    provider = DynamicCandidateProvider(executor)
    node = tree.get("sdk.install.java.{identifier}")
    first = await provider.provide(node, session)
    second = await provider.provide(node, session)
    assert first.candidates[0].token == "17.0.10-tem"
    assert executor.calls == 1
    provider.invalidate_after_command("sdk install java 17.0.10-tem", True)
    await provider.provide(node, session)
    assert executor.calls == 2


@pytest.mark.asyncio
async def test_dynamic_failure_returns_error():
    tree = load_command_tree(SDKMAN_TREE)
    executor = FakeExecutor("", ok=False)
    provider = DynamicCandidateProvider(executor)
    result = await provider.provide(tree.get("sdk.install.java.{identifier}"), CommandSession(tree))
    assert result.candidates == ()
    assert result.error.code == "command_failed"
