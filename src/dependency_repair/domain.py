"""The rules and result types. Pure: no files, no environment, no processes."""
from __future__ import annotations

import enum
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement


class RepairPolicy(enum.Enum):
    """What to do when requirements are unmet."""

    AUTO = "auto"  # install them, and say so
    PROMPT = "prompt"  # show the list and the target environment, install only on a yes
    OFF = "off"  # report them and the manual command; install nothing


def parse_policy(raw: str | None) -> RepairPolicy | None:
    """The policy named by ``raw`` (``auto``/``prompt``/``off``, any case), or None when absent or not one of them."""
    if raw is None:
        return None
    try:
        return RepairPolicy(raw.strip().lower())
    except ValueError:
        return None


class Outcome(enum.Enum):
    UP_TO_DATE = "up_to_date"  # every declared requirement is met
    INSTALLED = "installed"  # the unmet ones were installed
    SKIPPED = "skipped"  # nothing to check: the source declares no requirements for this install
    CHECK_FAILED = "check_failed"  # the declared requirements could not be read or understood
    DISABLED = "disabled"  # unmet, and the policy is OFF
    DECLINED = "declined"  # unmet, the policy is PROMPT, and nobody said yes (or nobody could be asked)
    INSTALL_FAILED = "install_failed"  # unmet, and installing them did not work


@dataclass(frozen=True)
class RepairResult:
    outcome: Outcome
    unmet: tuple[str, ...] = ()
    detail: str = ""

    @property
    def satisfied(self) -> bool:
        """The environment meets every declared requirement now."""
        return self.outcome in (Outcome.UP_TO_DATE, Outcome.INSTALLED)


@dataclass(frozen=True)
class InstallResult:
    ok: bool
    detail: str = ""


class InvalidRequirementError(ValueError):
    """A declared requirement string is not valid, so it cannot be checked or installed."""


def find_unmet(specs: Iterable[str], installed_version: Callable[[str], str | None]) -> tuple[str, ...]:
    """The requirement strings in ``specs`` that are missing or too old.

    A requirement whose environment marker is false here (``; sys_platform == "linux"`` on Windows) is not unmet.
    A pre-release counts as satisfying a range, matching what ``pip`` will have installed.
    """
    unmet: list[str] = []
    for spec in specs:
        try:
            req = Requirement(spec)
        except InvalidRequirement as exc:
            raise InvalidRequirementError(f"{spec!r}: {exc}") from exc
        if req.marker is not None and not req.marker.evaluate():
            continue
        version = installed_version(req.name)
        if version is None or (req.specifier and not req.specifier.contains(version, prereleases=True)):
            unmet.append(spec)
    return tuple(unmet)
