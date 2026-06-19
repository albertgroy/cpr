import json
import subprocess
from urllib.error import URLError

import pytest

from cpr.cli.api import ApiClient, ApiError
from cpr.cli.main import _validate_template, find_help, main, render_response


class FakeRun:
    def __init__(self, returncode=0, stdout="help"):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_find_help_longest_prefix(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["tool", "a", "b", "--help"]:
            return FakeRun(1, "")
        return FakeRun(0, "ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = find_help("tool", ["a", "b"])
    assert result["sub_path"] == ["a"]
    assert calls[0] == ["tool", "a", "b", "--help"]


def test_find_help_not_found(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeRun(1, ""))
    with pytest.raises(ApiError) as exc:
        find_help("missing", [])
    assert exc.value.code == "HELP_NOT_FOUND"
    assert exc.value.exit_code == 2


def test_validate_template_blocks_shell_meta_and_bad_placeholder():
    _validate_template({"exec_template": "sdk install java {identifier}", "exec_template_args": {"identifier": {"from": "candidates", "kind": "id"}}})
    with pytest.raises(ApiError):
        _validate_template({"exec_template": "rm -rf {path}; echo bad", "exec_template_args": {"path": {}}})
    with pytest.raises(ApiError):
        _validate_template({"exec_template": "cmd {Bad}", "exec_template_args": {"Bad": {}}})
    with pytest.raises(ApiError):
        _validate_template({"exec_template": "cmd {name}", "exec_template_args": {}})


def test_render_response_flag_candidate_preserved():
    text = render_response("git", ["status"], {"result": {"summary": "s", "usage": "git status", "candidates": [{"token": "--password", "desc": "flag name", "kind": "flag"}], "danger": False}})
    assert "--password" in text


def test_api_client_network_error(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError("down")

    monkeypatch.setattr("cpr.cli.api.urlopen", fail)
    with pytest.raises(ApiError) as exc:
        ApiClient("http://server").resolve({})
    assert exc.value.code == "NETWORK_UNREACHABLE"
    assert exc.value.exit_code == 3


def test_main_cache_hit_no_api(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CPR_HOME", str(tmp_path))
    (tmp_path / "config").write_text("client:\n  id: 00000000-0000-4000-8000-000000000001\n  locale: en-US\ncache:\n  dir: " + str(tmp_path / "cache") + "\n", encoding="utf-8")
    monkeypatch.setattr("cpr.cli.main.find_help", lambda *a, **k: {"sub_path": ["status"], "help_text": "help", "help_source": "git status --help", "help_truncated_at_size": None})
    from cpr.cli.cache import ClientCache, cache_key
    cache = ClientCache(tmp_path / "cache" / "cache.sqlite")
    response = {"schema_version": "1", "prompt_version": "p1", "result": {"summary": "cached", "usage": "git status", "danger": False}}
    cache.put(cache_key("git", ["status"], "help", "en-US", "unknown"), "unknown", response)
    cache.close()
    monkeypatch.setattr("cpr.cli.main.ApiClient.resolve", lambda *a, **k: (_ for _ in ()).throw(AssertionError("api called")))
    assert main(["git", "status"]) == 0
    assert "cached" in capsys.readouterr().out


def test_main_server_error_exit(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CPR_HOME", str(tmp_path))
    monkeypatch.setattr("cpr.cli.main.find_help", lambda *a, **k: {"sub_path": [], "help_text": "help", "help_source": "x --help", "help_truncated_at_size": None})
    monkeypatch.setattr("cpr.cli.main.ApiClient.resolve", lambda *a, **k: (_ for _ in ()).throw(ApiError("QUOTA_EXCEEDED", "quota", {"quota": {"used": 50, "limit": 50}, "error": {"retry_after_seconds": 7200}})))
    assert main(["x"]) == 4
    assert "50/50" in capsys.readouterr().err
