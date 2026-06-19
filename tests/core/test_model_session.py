from cpr.core.builtin_tree import SDKMAN_TREE
from cpr.core.model import load_command_tree, load_command_tree_file
from cpr.core.session import CommandSession, SessionResult


def test_load_tree_links_and_defaults_execute():
    tree = load_command_tree(SDKMAN_TREE)
    node = tree.get("sdk.list.java")
    assert node.execute.command == "sdk list java"
    assert tree.get("sdk").children[0].id == "sdk.list"


def test_load_tree_file(tmp_path):
    path = tmp_path / "tree.yaml"
    path.write_text("nodes:\n  - id: sdk\n    tokens: [sdk]\n", encoding="utf-8")
    assert load_command_tree_file(path).get("sdk").id == "sdk"


def test_invalid_id_rejected():
    raw = {"nodes": [{"id": "Sdk", "tokens": ["Sdk"]}]}
    try:
        load_command_tree(raw)
    except ValueError as exc:
        assert "invalid" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_longest_prefix_and_unparsed_tail():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    session.set_tokens(["sdk", "list", "java", "--bad"])
    assert session.current_node.id == "sdk.list.java"
    assert session.unparsed_tail == ["--bad"]


def test_param_match_longest_prefix():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    session.set_tokens(["sdk", "install", "java", "17.0.10-tem"])
    assert session.current_node.id == "sdk.install.java.{identifier}"
    assert session.unparsed_tail == []


def test_backspace_escape_and_result_ring():
    tree = load_command_tree(SDKMAN_TREE)
    session = CommandSession(tree)
    session.set_tokens(["sdk", "list", "java"])
    assert session.backspace("") == "java"
    assert session.current_node.id == "sdk.list"
    assert session.backspace("x") is None
    assert session.escape("abc") == ("clear-input", None)
    assert session.escape("") == ("pop-token", "list")
    for index in range(6):
        session.record_execution(f"cmd {index}", SessionResult(ok=bool(index), stderr=str(index)))
    assert len(session.results) == 5
    assert session.last_command == "cmd 5"
    assert session.last_result.stderr == "5"
