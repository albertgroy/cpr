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
        ROOT / "errors" / "help_not_found",
        ROOT / "errors" / "help_timeout",
        ROOT / "errors" / "bad_request",
        ROOT / "errors" / "invalid_client",
        ROOT / "errors" / "llm_parse_failed",
        ROOT / "errors" / "network_unreachable",
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
        "help_not_found": "HELP_NOT_FOUND",
        "help_timeout": "HELP_TIMEOUT",
        "bad_request": "BAD_REQUEST",
        "invalid_client": "INVALID_CLIENT",
        "llm_parse_failed": "LLM_PARSE_FAILED",
        "network_unreachable": "NETWORK_UNREACHABLE",
    }
    for name, code in codes.items():
        response = json.loads((ROOT / "errors" / name / "response.json").read_text(encoding="utf-8"))
        assert response["error"]["code"] == code
