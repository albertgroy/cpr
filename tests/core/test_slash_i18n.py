import logging

from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.model import load_command_tree
from cpr.core.session import CommandSession, SessionResult
from cpr.core.slash import SlashCommandParser
from cpr.i18n.loader import I18nLoader, resolve_locale


def test_slash_parse_regex_args():
    command = SlashCommandParser().parse("/ai 帮我安装 Java 17 LTS")
    assert command.name == "ai"
    assert command.args == "帮我安装 Java 17 LTS"


def test_back_and_clear_share_session_behavior():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    session.set_tokens(["sdk", "list"])
    session.display_buffer.append("x")
    session.record_execution("bad", SessionResult(False, stderr="err"))
    parser = SlashCommandParser()
    assert parser.handle("/back", session).ok
    assert session.current_tokens == ["sdk"]
    assert parser.handle("/clear", session).ok
    assert session.display_buffer == []
    assert session.last_command == "bad"
    assert session.last_result.stderr == "err"


def test_unknown_slash_not_history():
    result = SlashCommandParser().handle("/wat", CommandSession(load_command_tree(SDKMAN_TREE)))
    assert not result.ok
    assert not result.add_history


def test_fix_prompt_contains_last_command_and_stderr():
    session = CommandSession(load_command_tree(SDKMAN_TREE))
    session.record_execution("sdk list java", SessionResult(False, stderr="network error"))
    result = SlashCommandParser().handle("/fix", session)
    assert "sdk list java" in result.message
    assert "network error" in result.message


def test_resolve_locale_order():
    assert resolve_locale("en-US", {"CPR_LOCALE": "zh-CN", "LANG": "en_US.UTF-8"}) == "zh-CN"
    assert resolve_locale(None, {"LANG": "en_US.UTF-8"}) == "en-US"


def test_i18n_fallback_warns(caplog):
    loader = I18nLoader("zh-CN")
    with caplog.at_level(logging.WARNING):
        assert loader.node_text({"en-US": "Hello"}, "node.id") == "Hello"
    assert "fallback en-US" in caplog.text
