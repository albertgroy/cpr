from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml

ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9_{}-]+)*$")
PARAM_SOURCES = {"sdk.candidates.java.identifiers", "sdk.installed.java.versions"}


@dataclass(frozen=True)
class ParamSpec:
    name: str
    source: str


@dataclass(frozen=True)
class ExecuteSpec:
    command: str
    shell_mode: str = "bash-lc-source"


@dataclass
class CommandNode:
    id: str
    tokens: tuple[str, ...]
    title: dict[str, str] = field(default_factory=dict)
    desc: dict[str, str] = field(default_factory=dict)
    child_ids: tuple[str, ...] = field(default_factory=tuple)
    children: tuple[CommandNode, ...] = field(default_factory=tuple)
    param: ParamSpec | None = None
    execute: ExecuteSpec | None = None

    @property
    def token(self) -> str:
        return self.tokens[-1] if self.tokens else ""

    @property
    def executable(self) -> bool:
        return self.execute is not None


@dataclass(frozen=True)
class CommandTree:
    nodes: dict[str, CommandNode]
    root_ids: tuple[str, ...]

    def get(self, node_id: str) -> CommandNode:
        return self.nodes[node_id]

    def match_longest(self, tokens: list[str]) -> tuple[CommandNode | None, list[str]]:
        matched: CommandNode | None = None
        matched_len = 0
        for index in range(1, len(tokens) + 1):
            node_id = ".".join(tokens[:index])
            node = self.nodes.get(node_id)
            if node:
                matched = node
                matched_len = index
                continue
            param_node = self._match_param(tokens[:index])
            if param_node:
                matched = param_node
                matched_len = index
        return matched, tokens[matched_len:]

    def _match_param(self, tokens: list[str]) -> CommandNode | None:
        if not tokens:
            return None
        parent_id = ".".join(tokens[:-1])
        for node in self.nodes.values():
            if node.param and len(node.tokens) == len(tokens) and ".".join(node.tokens[:-1]) == parent_id:
                return node
        return None


def load_command_tree_file(path: str | Path) -> CommandTree:
    with Path(path).open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, dict):
        raise ValueError("command tree yaml must be object")
    return load_command_tree(raw)


def load_command_tree(raw: dict[str, Any]) -> CommandTree:
    node_items = raw.get("nodes")
    if not isinstance(node_items, list):
        raise ValueError("command tree requires nodes list")
    nodes = {_parse_node(item).id: _parse_node(item) for item in node_items}
    if len(nodes) != len(node_items):
        raise ValueError("duplicate command node id")
    for node in nodes.values():
        linked = []
        for child_id in node.child_ids:
            child = nodes.get(child_id)
            if not child:
                raise ValueError(f"missing child node {child_id}")
            linked.append(child)
        node.children = tuple(linked)
    child_ids = {child_id for node in nodes.values() for child_id in node.child_ids}
    root_ids = tuple(node_id for node_id in nodes if node_id not in child_ids)
    return CommandTree(nodes=nodes, root_ids=root_ids)


def _parse_node(item: dict[str, Any]) -> CommandNode:
    node_id = _required_str(item, "id")
    if not ID_PATTERN.fullmatch(node_id):
        raise ValueError(f"invalid command node id: {node_id}")
    tokens_value = item.get("tokens")
    if not isinstance(tokens_value, list) or not all(isinstance(token, str) for token in tokens_value):
        raise ValueError(f"node {node_id} requires string tokens")
    tokens = tuple(tokens_value)
    if node_id != ".".join(tokens):
        raise ValueError(f"node {node_id} id must equal tokens joined by dots")
    child_ids_value = item.get("children", [])
    if not isinstance(child_ids_value, list) or not all(isinstance(child_id, str) for child_id in child_ids_value):
        raise ValueError(f"node {node_id} children must be id list")
    param = _parse_param(node_id, tokens, item.get("param"))
    execute = _parse_execute(tokens, item.get("execute"))
    return CommandNode(
        id=node_id,
        tokens=tokens,
        title=_locale_map(item.get("title", {})),
        desc=_locale_map(item.get("desc", {})),
        child_ids=tuple(child_ids_value),
        param=param,
        execute=execute,
    )


def _parse_param(node_id: str, tokens: tuple[str, ...], raw: Any) -> ParamSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"node {node_id} param must be object")
    last = tokens[-1]
    if not re.fullmatch(r"\{[a-z][a-z0-9_-]*\}", last):
        raise ValueError(f"node {node_id} param token must be {{name}}")
    name = last[1:-1]
    source = _required_str(raw, "source")
    if source not in PARAM_SOURCES:
        raise ValueError(f"unsupported param source: {source}")
    return ParamSpec(name=name, source=source)


def _parse_execute(tokens: tuple[str, ...], raw: Any) -> ExecuteSpec | None:
    if raw is False or raw is None:
        return None
    if raw is True:
        return ExecuteSpec(command=" ".join(tokens))
    if not isinstance(raw, dict):
        raise ValueError("execute must be object, true, false, or omitted")
    command = raw.get("command") or " ".join(tokens)
    shell_mode = raw.get("shell_mode", "bash-lc-source")
    if shell_mode not in {"direct", "bash-lc-source"}:
        raise ValueError(f"unsupported shell_mode: {shell_mode}")
    return ExecuteSpec(command=str(command), shell_mode=str(shell_mode))


def _locale_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing string field: {key}")
    return value
