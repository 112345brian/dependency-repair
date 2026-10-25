"""In-memory fakes for the ports, for tests of code that takes them."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from dep_heal.domain import InstallResult
from dep_heal.ports import SourceError


@dataclass
class FakeSource:
    requirements: Sequence[str] | None = ()
    error: str | None = None

    def declared(self) -> Sequence[str] | None:
        if self.error is not None:
            raise SourceError(self.error)
        return self.requirements


@dataclass
class FakeEnvironment:
    versions: Mapping[str, str] = field(default_factory=lambda: {})
    installer_present: bool = True
    where: str = "fake-env"

    def installed_version(self, name: str) -> str | None:
        return self.versions.get(name)

    def can_install(self) -> bool:
        return self.installer_present

    def target(self) -> str:
        return self.where


@dataclass
class FakeInstaller:
    result: InstallResult = field(default_factory=lambda: InstallResult(True))
    calls: list[tuple[str, ...]] = field(default_factory=lambda: [])

    def install(self, requirements: Sequence[str]) -> InstallResult:
        self.calls.append(tuple(requirements))
        return self.result


@dataclass
class FakeConsole:
    is_interactive: bool = True
    answer: bool = True
    messages: list[str] = field(default_factory=lambda: [])
    questions: list[str] = field(default_factory=lambda: [])

    @property
    def interactive(self) -> bool:
        return self.is_interactive

    def say(self, message: str) -> None:
        self.messages.append(message)

    def confirm(self, question: str) -> bool:
        self.questions.append(question)
        return self.answer
