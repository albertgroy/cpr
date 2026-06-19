import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "server"


def test_fixture_three_file_layout():
    expected = [
        ROOT / "scenarios" / "sdk_root",
        ROOT / "scenarios" / "sdk_install_java",
        ROOT / "scenarios" / "git_status",
        ROOT / "scenarios" / "kubectl_apply",
        ROOT / "errors" / "quota_exceeded",
        ROOT / "errors" / "llm_timeout",
        ROOT / "errors" / "server_error",
        ROOT / "errors" / "invalid_template",
        ROOT / "errors" / "schema_mismatch",
    ]
    for directory in expected:
        assert (directory / "request.json").exists()
        assert (directory / "response.json").exists()
        assert (directory / "notes.md").exists()
        assert json.loads((directory / "request.json").read_text(encoding="utf-8"))["schema_version"] == "1"


def test_error_fixture_codes():
    codes = {
        "quota_exceeded": "QUOTA_EXCEEDED",
        "llm_timeout": "LLM_TIMEOUT",
        "server_error": "SERVER_ERROR",
        "schema_mismatch": "SCHEMA_MISMATCH",
    }
    for name, code in codes.items():
        response = json.loads((ROOT / "errors" / name / "response.json").read_text(encoding="utf-8"))
        assert response["error"]["code"] == code
