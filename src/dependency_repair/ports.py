"""What the use case needs from the outside world, as it needs it. Adapters implement these; nothing here does I/O."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from dependency_repair.domain import InstallResult


class SourceError(Exception):
    """The declared requirements exist but could not be read (unreadable file, malformed TOML)."""


class RequirementSource(Protocol):
    def declared(self) -> Sequence[str] | None:
        """The requirement strings this install should have, or None when this source has none to offer
        (not an editable install, the checkout is gone). Raises ``SourceError`` when they exist but cannot be read."""
        ...


class Environment(Protocol):
    def installed_version(self, name: str) -> str | None:
        """The installed version of a distribution, or None when it is not installed."""
        ...

    def can_install(self) -> bool:
        """Whether this environment has an installer at all (a ``uv``-managed venv has no ``pip``)."""
        ...

    def target(self) -> str:
        """A human name for where packages would go, shown before a prompt."""
        ...


class Installer(Protocol):
    def install(self, requirements: Sequence[str]) -> InstallResult:
        """Install the requirement strings. Never raises: a failure is ``InstallResult(ok=False)``."""
        ...


class Console(Protocol):
    @property
    def interactive(self) -> bool:
        """Whether a person can be asked a question right now (a scheduled task or a windowless process cannot)."""
        ...

    def say(self, message: str) -> None: ...

    def confirm(self, question: str) -> bool:
        """Ask a yes/no question. Only called when ``interactive``; the default answer is no."""
        ...


# Starts ``argv`` to completion with the caller's own streams and returns its exit code, or None when it could not
# be started. The caller binds this; the package never starts a process on its own account.
CommandRunner = Callable[[Sequence[str]], int | None]
