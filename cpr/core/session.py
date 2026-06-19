from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from cpr.core.model import CommandNode, CommandTree


@dataclass(frozen=True)
class SessionResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class CommandSession:
    def __init__(self, tree: CommandTree, result_limit: int = 5) -> None:
        self.tree = tree
        self.current_tokens: list[str] = []
        self.current_node: CommandNode | None = None
        self.unparsed_tail: list[str] = []
        self.last_command: str | None = None
        self.results: deque[SessionResult] = deque(maxlen=result_limit)
        self.display_buffer: list[str] = []
        self.history: list[str] = []

    @property
    def last_result(self) -> SessionResult | None:
        return self.results[-1] if self.results else None

    def set_tokens(self, tokens: list[str]) -> None:
        self.current_tokens = list(tokens)
        self._resolve()

    def append_token(self, token: str) -> None:
        self.current_tokens.append(token)
        self._resolve()

    def pop_token(self) -> str | None:
        if not self.current_tokens:
            return None
        token = self.current_tokens.pop()
        self._resolve()
        return token

    def backspace(self, input_text: str) -> str | None:
        if input_text:
            return None
        return self.pop_token()

    def escape(self, input_text: str) -> tuple[str, str | None]:
        if input_text:
            return "clear-input", None
        popped = self.pop_token()
        return "pop-token", popped

    def record_execution(self, command: str, result: SessionResult) -> None:
        self.last_command = command
        self.results.append(result)

    def clear_display(self) -> None:
        self.display_buffer.clear()

    def _resolve(self) -> None:
        self.current_node, self.unparsed_tail = self.tree.match_longest(self.current_tokens)
