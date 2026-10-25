"""Install requirements with ``python -m pip``, started through a caller-supplied command runner."""
from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

from dependency_repair.domain import InstallResult
from dependency_repair.ports import CommandRunner


class PipInstaller:
    def __init__(self, run_command: CommandRunner, python: str | None = None) -> None:
        self._run_command = run_command
        self._python = python or sys.executable

    def install(self, requirements: Sequence[str]) -> InstallResult:
        argv = (self._python, "-m", "pip", "install", "--disable-pip-version-check", *requirements)
        returncode = self._run_command(argv)
        if returncode is None:
            return InstallResult(False, "pip could not be started")
        if returncode != 0:
            return InstallResult(False, f"pip exited {returncode}")
        # What pip just wrote is not on any import finder's cache yet.
        importlib.invalidate_caches()
        return InstallResult(True)
