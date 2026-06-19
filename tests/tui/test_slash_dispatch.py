"""Slash dispatch into content_buffer (archi 推荐 P2 单测)."""
from __future__ import annotations

from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.model import load_command_tree
from cpr.core.session import CommandSession
from cpr.core.slash import SlashCommandParser
from cpr.i18n import I18nLoader
from cpr.tui.app import WorkspaceState, dispatch_slash


class _FakeBuffer:
    def __init__(self, text: str = "") -> None:
        self.text = text


def _state():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree=tree)
    return WorkspaceState(session=session, i18n=I18nLoader(locale="zh-CN"), candidates=[])


def test_help_writes_to_content_buffer():
    parser = SlashCommandParser()
    buffer = _FakeBuffer("seed\n")
    state = _state()

    written = dispatch_slash(parser, state, buffer, "/help")

    assert written is True
    assert buffer.text.startswith("seed\n")
    assert "/help" in buffer.text
    assert "/ai" in buffer.text  # help message lists known slash commands


def test_unknown_slash_does_not_write():
    parser = SlashCommandParser()
    buffer = _FakeBuffer("untouched\n")
    state = _state()

    written = dispatch_slash(parser, state, buffer, "/nope")

    assert written is False
    assert buffer.text == "untouched\n"


def test_non_slash_text_does_not_write():
    parser = SlashCommandParser()
    buffer = _FakeBuffer("untouched\n")
    state = _state()

    written = dispatch_slash(parser, state, buffer, "sdk install")

    assert written is False
    assert buffer.text == "untouched\n"


def test_back_writes_and_pops_token():
    parser = SlashCommandParser()
    buffer = _FakeBuffer("")
    state = _state()
    state.session.append_token("sdk")
    state.session.append_token("install")

    written = dispatch_slash(parser, state, buffer, "/back")

    assert written is True
    assert state.session.current_tokens == ["sdk"]
    assert "/back" in buffer.text
