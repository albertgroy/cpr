from __future__ import annotations

from dataclasses import dataclass
import re

from cpr.core.session import CommandSession

SLASH_PATTERN = re.compile(r"^/(\w+)(?:\s+(.*))?$")
KNOWN = {"ai", "explain", "fix", "help", "clear", "back"}


@dataclass(frozen=True)
class SlashCommand:
    name: str
    args: str


@dataclass(frozen=True)
class SlashCommandResult:
    ok: bool
    message: str
    command: SlashCommand | None = None
    add_history: bool = True


class SlashCommandParser:
    def parse(self, text: str) -> SlashCommand | None:
        match = SLASH_PATTERN.fullmatch(text)
        if not match:
            return None
        return SlashCommand(name=match.group(1).lower(), args=match.group(2) or "")

    def handle(self, text: str, session: CommandSession) -> SlashCommandResult:
        command = self.parse(text)
        if command is None:
            return SlashCommandResult(False, "not a slash command", add_history=False)
        if command.name not in KNOWN:
            return SlashCommandResult(False, f"unknown slash command: /{command.name}", command, False)
        if command.name == "back":
            session.pop_token()
            return SlashCommandResult(True, "back", command)
        if command.name == "clear":
            session.clear_display()
            return SlashCommandResult(True, "clear", command)
        if command.name == "help":
            return SlashCommandResult(True, "/ai /explain /fix /help /clear /back", command)
        if command.name == "fix":
            last = session.last_result
            stderr = last.stderr if last else ""
            return SlashCommandResult(True, f"mock fix prompt: {session.last_command or ''}\n{stderr}", command)
        return SlashCommandResult(True, f"mock /{command.name}: {command.args}", command)
