"""In-memory fakes for the ports, for tests of code that takes them."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from dependency_repair.domain import InstallPlan, InstallResult
from dependency_repair.ports import SourceError


@dataclass
class FakeSource:
    requirements: Sequence[str] | None = ()
    groups: Mapping[str, Sequence[str]] = field(default_factory=lambda: {})
    error: str | None = None
    asked_extras: list[tuple[str, ...]] = field(default_factory=lambda: [])

    def declared(self, extras: Sequence[str]) -> Sequence[str] | None:
        self.asked_extras.append(tuple(extras))
        if self.error is not None:
            raise SourceError(self.error)
        if self.requirements is None:
            return None
        specs = list(self.requirements)
        for extra in extras:
            if extra not in self.groups:
                raise SourceError(f"no group {extra}")
            specs += self.groups[extra]
        return specs


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
    plan_result: InstallPlan = field(default_factory=lambda: InstallPlan())
    calls: list[tuple[str, ...]] = field(default_factory=lambda: [])
    planned: list[tuple[str, ...]] = field(default_factory=lambda: [])

    def plan(self, requirements: Sequence[str]) -> InstallPlan:
        self.planned.append(tuple(requirements))
        return self.plan_result

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
