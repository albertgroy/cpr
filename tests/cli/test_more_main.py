import json
from urllib.error import HTTPError, URLError
from io import BytesIO

import pytest

from cpr.cli.api import ApiClient, ApiError
from cpr.cli.main import _fixture_help, _payload, main


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeHTTPError(HTTPError):
    def __init__(self, payload):
        super().__init__("url", 429, "quota", {}, BytesIO(json.dumps(payload).encode("utf-8")))


def test_api_client_success_and_http_error(monkeypatch):
    monkeypatch.setattr("cpr.cli.api.urlopen", lambda *a, **k: FakeResponse({"schema_version": "1"}))
    assert ApiClient("http://server").resolve({}) == {"schema_version": "1"}

    def fail(*args, **kwargs):
        raise FakeHTTPError({"error": {"code": "QUOTA_EXCEEDED", "message": "quota"}})

    monkeypatch.setattr("cpr.cli.api.urlopen", fail)
    with pytest.raises(ApiError) as exc:
        ApiClient("http://server").resolve({})
    assert exc.value.code == "QUOTA_EXCEEDED"


def test_quota_and_diag(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CPR_HOME", str(tmp_path))
    monkeypatch.setattr("cpr.cli.main.ApiClient.quota", lambda self, client_id: {"used": 1, "limit": 50})
    assert main(["--quota"]) == 0
    assert "used" in capsys.readouterr().out
    assert main(["--diag"]) == 0
    assert "schema_version=1" in capsys.readouterr().out


def test_main_bad_tool_and_no_args(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out
    assert main(["../bad"]) == 2


def test_main_miss_invalid_template(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CPR_HOME", str(tmp_path))
    monkeypatch.setattr("cpr.cli.main.find_help", lambda *a, **k: {"sub_path": [], "help_text": "help", "help_source": "x --help", "help_truncated_at_size": None})
    monkeypatch.setattr("cpr.cli.main.ApiClient.resolve", lambda *a, **k: {"schema_version": "1", "prompt_version": "p", "result": {"danger": True, "exec_template": "bad;cmd", "exec_template_args": {}}})
    assert main(["x"]) == 5
    assert "模板" in capsys.readouterr().err


def test_danger_no_and_yes(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CPR_HOME", str(tmp_path))
    monkeypatch.setattr("cpr.cli.main.find_help", lambda *a, **k: {"sub_path": ["install", "java"], "help_text": "help", "help_source": "sdk install java --help", "help_truncated_at_size": None})
    response = {"schema_version": "1", "prompt_version": "p", "result": {"summary": "s", "usage": "sdk install java <identifier>", "candidates": [{"token": "17.0.10-tem", "kind": "id", "desc": ""}], "danger": True, "danger_reason": "writes", "exec_template": "sdk install java {identifier}", "exec_template_args": {"identifier": {"from": "candidates", "kind": "id"}}, "exec_shell_mode": "direct"}}
    monkeypatch.setattr("cpr.cli.main.ApiClient.resolve", lambda *a, **k: response)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert main(["sdk", "install", "java"]) == 0
    assert "danger" in capsys.readouterr().out

    class Done:
        exit_code = 7
        stdout = "out\n"
        stderr = "err\n"

    monkeypatch.setattr("cpr.cli.main.Executor.run_sync", lambda self, cmd, mode: Done())
    assert main(["-y", "sdk", "install", "java"]) == 7
    output = capsys.readouterr()
    assert "out" in output.out
    assert "err" in output.err


def test_fixture_help_and_payload(tmp_path):
    assert _fixture_help("__quota", [])["sub_path"] == []
    assert _fixture_help("git", ["status"])["sub_path"] == ["status"]
    payload = _payload(tmp_path, {"client": {"id": "id"}, "redact": {}}, "en-US", "mysql", ["-p", "secret"], {"sub_path": [], "help_text": "h", "help_source": "mysql --help", "help_truncated_at_size": None})
    assert payload["args"] == ["-p", "<REDACTED>"]
