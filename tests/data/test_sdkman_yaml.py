"""Structural assertions on data/sdkman.yaml.

These tests cover the data file itself: presence of the 7 T-001 commands,
locale completeness for zh-CN, param sources from the enumerated allow-list,
and shell_mode on every executable terminal. Loader behaviour (parse + link
+ error paths) is covered by agent1's tests/core/test_node_loader.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "sdkman.yaml"

REQUIRED_EXECUTABLE_IDS: tuple[str, ...] = (
    "sdk",
    "sdk.list",
    "sdk.list.java",
    "sdk.install.java.{identifier}",
    "sdk.use.java.{version}",
    "sdk.default.java.{version}",
    "sdk.current.java",
)

ALLOWED_PARAM_SOURCES = {
    "sdk.candidates.java.identifiers",
    "sdk.installed.java.versions",
}


@pytest.fixture(scope="module")
def raw() -> dict:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def nodes_by_id(raw: dict) -> dict[str, dict]:
    items = raw.get("nodes")
    assert isinstance(items, list) and items, "nodes must be a non-empty list"
    by_id = {item["id"]: item for item in items}
    assert len(by_id) == len(items), "duplicate node id in sdkman.yaml"
    return by_id


def test_data_file_exists() -> None:
    assert DATA_PATH.is_file(), f"missing data file: {DATA_PATH}"


def test_required_commands_present(nodes_by_id: dict[str, dict]) -> None:
    missing = [node_id for node_id in REQUIRED_EXECUTABLE_IDS if node_id not in nodes_by_id]
    assert not missing, f"missing required command nodes: {missing}"


def test_id_equals_tokens_joined(nodes_by_id: dict[str, dict]) -> None:
    for node_id, item in nodes_by_id.items():
        tokens = item.get("tokens")
        assert isinstance(tokens, list) and tokens, f"{node_id} missing tokens"
        joined = ".".join(tokens)
        assert joined == node_id, f"{node_id} != tokens joined ({joined})"


def test_children_reference_existing_nodes(nodes_by_id: dict[str, dict]) -> None:
    for node_id, item in nodes_by_id.items():
        for child_id in item.get("children", []) or []:
            assert child_id in nodes_by_id, f"{node_id} -> unknown child {child_id}"


def test_param_nodes_use_allowed_sources(nodes_by_id: dict[str, dict]) -> None:
    param_ids = [node_id for node_id, item in nodes_by_id.items() if item.get("param")]
    assert param_ids, "expected at least one param node"
    for node_id in param_ids:
        item = nodes_by_id[node_id]
        last = item["tokens"][-1]
        assert last.startswith("{") and last.endswith("}"), (
            f"{node_id} param tail token must be {{name}}, got {last}"
        )
        source = item["param"]["source"]
        assert source in ALLOWED_PARAM_SOURCES, (
            f"{node_id} param source {source} not in {ALLOWED_PARAM_SOURCES}"
        )


def test_required_executables_declare_shell_mode(nodes_by_id: dict[str, dict]) -> None:
    for node_id in REQUIRED_EXECUTABLE_IDS:
        execute = nodes_by_id[node_id].get("execute")
        assert isinstance(execute, dict), (
            f"{node_id} should declare execute as object with shell_mode"
        )
        assert execute.get("shell_mode") == "bash-lc-source", (
            f"{node_id} shell_mode must be bash-lc-source for SDKMAN"
        )


def test_zh_cn_locale_complete(nodes_by_id: dict[str, dict]) -> None:
    """zh-CN copy is mandatory; en-US placeholders are allowed in MVP."""
    for node_id, item in nodes_by_id.items():
        title = item.get("title", {}) or {}
        desc = item.get("desc", {}) or {}
        assert title.get("zh-CN"), f"{node_id} missing zh-CN title"
        assert desc.get("zh-CN"), f"{node_id} missing zh-CN desc"


def test_en_us_keys_present_even_if_placeholder(nodes_by_id: dict[str, dict]) -> None:
    """en-US should at least appear so i18n loader sees the key (warn instead of fallback to id)."""
    for node_id, item in nodes_by_id.items():
        title = item.get("title", {}) or {}
        desc = item.get("desc", {}) or {}
        assert "en-US" in title, f"{node_id} missing en-US title key"
        assert "en-US" in desc, f"{node_id} missing en-US desc key"


def test_root_is_sdk(nodes_by_id: dict[str, dict]) -> None:
    referenced_as_child: set[str] = set()
    for item in nodes_by_id.values():
        for child_id in item.get("children", []) or []:
            referenced_as_child.add(child_id)
    roots = [node_id for node_id in nodes_by_id if node_id not in referenced_as_child]
    assert roots == ["sdk"], f"expected single root 'sdk', got {roots}"
