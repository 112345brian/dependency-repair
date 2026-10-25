"""A person at a terminal: messages go to stderr, questions are read from stdin."""
from __future__ import annotations

import sys
from typing import TextIO


class TerminalConsole:
    def __init__(self, stdin: TextIO | None = None, stderr: TextIO | None = None) -> None:
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stderr = stderr if stderr is not None else sys.stderr

    @property
    def interactive(self) -> bool:
        # A windowless process (``pythonw``, a scheduled task) has no stdin at all; a pipe is not a person either.
        stream = self._stdin
        return stream is not None and bool(getattr(stream, "isatty", lambda: False)())

    def say(self, message: str) -> None:
        stream = self._stderr
        if stream is not None:
            print(message, file=stream, flush=True)

    def confirm(self, question: str) -> bool:
        self.say(f"{question} [y/N] ")
        try:
            answer = self._stdin.readline()
        except (OSError, ValueError):
            return False
        return answer.strip().lower() in ("y", "yes")
