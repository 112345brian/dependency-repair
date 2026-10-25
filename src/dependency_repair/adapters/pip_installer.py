"""Install requirements with ``python -m pip``, started through a caller-supplied command runner."""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from dependency_repair.domain import InstallPlan, InstallResult
from dependency_repair.ports import CommandRunner


class PipInstaller:
    def __init__(self, run_command: CommandRunner, python: str | None = None) -> None:
        self._run_command = run_command
        self._python = python or sys.executable

    def plan(self, requirements: Sequence[str]) -> InstallPlan:
        """Ask pip what it would install, resolving dependencies, without changing anything (pip 22.2 or newer).

        pip writes its report to a file, not stdout: stdout is encoded by the console's code page, a file is UTF-8.
        """
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            argv = (
                self._python, "-m", "pip", "install", "--disable-pip-version-check", "--dry-run", "--quiet",
                "--report", str(report_path), *requirements,
            )
            if self._run_command(argv) != 0:
                return InstallPlan()
            try:
                report: object = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return InstallPlan()
        packages = _packages_in_report(report)
        return InstallPlan(packages, known=True) if packages is not None else InstallPlan()

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


def _packages_in_report(report: object) -> tuple[str, ...] | None:
    """``name==version`` for each entry of a pip installation report's ``install`` list; None if it is not one."""
    if not isinstance(report, dict):
        return None
    items = cast("dict[str, object]", report).get("install")
    if not isinstance(items, list):
        return None
    packages: list[str] = []
    for item in cast("list[object]", items):
        if not isinstance(item, dict):
            return None
        meta = cast("dict[str, object]", item).get("metadata")
        if not isinstance(meta, dict):
            return None
        fields = cast("dict[str, object]", meta)
        name, version = fields.get("name"), fields.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            return None
        packages.append(f"{name}=={version}")
    return tuple(packages)
