from __future__ import annotations

import pytest


@pytest.fixture
def fixture_help():
    def _fixture_help(tool: str, args: list[str]) -> dict | None:
        if tool.startswith("__"):
            return {"sub_path": [], "help_text": f"usage: {tool}", "help_source": f"{tool} --help", "help_truncated_at_size": None}
        scenarios = {("sdk", ("install", "java")): ["install", "java"], ("git", ("status",)): ["status"], ("kubectl", ("apply",)): ["apply"], ("sdk", ()): []}
        for (fixture_tool, fixture_args), sub_path in scenarios.items():
            if tool == fixture_tool and tuple(args[: len(fixture_args)]) == fixture_args:
                return {"sub_path": sub_path, "help_text": f"usage: {tool} {' '.join(sub_path)}", "help_source": f"{tool} {' '.join(sub_path)} --help", "help_truncated_at_size": None}
        return None

    return _fixture_help
