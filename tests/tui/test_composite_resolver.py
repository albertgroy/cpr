"""Verify run_app's composite resolver routes param nodes to dynamic provider.

archi T-001 终验缺口 A 配套单测。
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from cpr.core.candidates import (
    Candidate as CoreCandidate,
    CandidateError,
    CandidateResult,
)
from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.model import load_command_tree
from cpr.core.session import CommandSession
from cpr.i18n import I18nLoader
from cpr.tui.app import make_composite_resolver
from cpr.tui.candidates import static_resolver


def _setup(tokens):
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree=tree)
    for token in tokens:
        session.append_token(token)
    return session, I18nLoader(locale="zh-CN")


def test_composite_routes_param_child_to_dynamic():
    session, i18n = _setup(["sdk", "install", "java"])
    dyn = AsyncMock()
    dyn.provide = AsyncMock(
        return_value=CandidateResult(
            candidates=(CoreCandidate(token="17.0.19-tem", label="17.0.19-tem", source="dynamic"),)
        )
    )
    composite = make_composite_resolver(dyn, static_resolver)

    candidates = asyncio.run(composite(session, i18n))

    assert dyn.provide.await_count == 1
    param_node = dyn.provide.await_args.args[0]
    assert param_node.id == "sdk.install.java.{identifier}"
    assert param_node.param is not None
    assert [c.token for c in candidates] == ["17.0.19-tem"]
    assert candidates[0].source == "dynamic"


def test_composite_routes_param_node_itself_to_dynamic():
    session, i18n = _setup(["sdk", "install", "java", "17.0.19-tem"])
    dyn = AsyncMock()
    dyn.provide = AsyncMock(return_value=CandidateResult(candidates=()))
    composite = make_composite_resolver(dyn, static_resolver)

    asyncio.run(composite(session, i18n))

    assert dyn.provide.await_count == 1
    param_node = dyn.provide.await_args.args[0]
    assert param_node.param is not None
    assert param_node.param.source == "sdk.candidates.java.identifiers"


def test_composite_falls_back_to_static_for_non_param_branch():
    session, i18n = _setup(["sdk", "list"])
    dyn = AsyncMock()
    dyn.provide = AsyncMock()
    composite = make_composite_resolver(dyn, static_resolver)

    candidates = asyncio.run(composite(session, i18n))

    dyn.provide.assert_not_awaited()
    assert [c.token for c in candidates] == ["java"]
    assert candidates[0].source == "static"


def test_composite_propagates_dynamic_error():
    session, i18n = _setup(["sdk", "install", "java"])
    dyn = AsyncMock()
    dyn.provide = AsyncMock(
        return_value=CandidateResult(
            candidates=(),
            error=CandidateError(code="parse_failed", message="boom"),
        )
    )
    composite = make_composite_resolver(dyn, static_resolver)

    with pytest.raises(RuntimeError, match="parse_failed: boom"):
        asyncio.run(composite(session, i18n))
