from cpr.cli.redact import redact_args, redact_value


def test_global_flags_space_and_equals():
    assert redact_args("curl", ["--token", "abc", "--api-key=def", "--password", "x", "--secret=y", "--key", "z"]) == ["--token", "<REDACTED>", "--api-key=<REDACTED>", "--password", "<REDACTED>", "--secret=<REDACTED>", "--key", "<REDACTED>"]


def test_per_tool_flags_mysql_vs_docker_and_ssh():
    assert redact_args("mysql", ["-p", "secret"]) == ["-p", "<REDACTED>"]
    assert redact_args("docker", ["-p", "8080:80"]) == ["-p", "8080:80"]
    assert redact_args("ssh", ["-i", "~/.ssh/id_rsa"]) == ["-i", "<REDACTED>"]
    assert redact_args("scp", ["-i=~/.ssh/id_rsa"]) == ["-i=<REDACTED>"]


def test_user_rules():
    config = {"extra_global_flags": ["--private"], "extra_per_tool": {"docker": {"redact_flags": ["--registry-password"]}}}
    assert redact_args("docker", ["--private", "x", "--registry-password=y"], config) == ["--private", "<REDACTED>", "--registry-password=<REDACTED>"]


def test_paths_users_and_private_paths(monkeypatch):
    monkeypatch.setenv("USER", "lee")
    assert redact_value("lee@example.com") == "<USER>@example.com"
    assert redact_value("other@example.com") == "other@example.com"
    assert redact_value("git@github.com") == "<USER>@github.com"
    assert redact_value("https://lee@example.com/repo") == "https://<USER>@example.com/repo"
    assert redact_value("/Users/lee/project") == "/Users/<USER>/project"
    assert redact_value("/home/lee/project") == "/home/<USER>/project"
    assert redact_value("~/.aws/credentials") == "<PRIVATE_PATH>"


def test_hash_whitelist_and_blob_boundaries():
    assert redact_value("a" * 40) == "a" * 40
    assert redact_value("abcdef1") == "abcdef1"
    assert redact_value("sha256:" + "a" * 64) == "sha256:" + "a" * 64
    assert redact_value("v17.0.10-tem") == "v17.0.10-tem"
    assert redact_value("A" * 39) == "A" * 39
    assert redact_value("A" * 40) == "<BLOB>"
    assert redact_value("abc123XYZ" * 5) == "<BLOB>"
