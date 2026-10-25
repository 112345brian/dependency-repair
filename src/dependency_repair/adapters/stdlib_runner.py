"""A ``CommandRunner`` on the standard library, for programs with no process-launching layer of their own.

A program that already has one (a launcher library, a project rule against raw ``subprocess``) binds its own
``CommandRunner`` instead and never imports this module.
"""
from __future__ import annotations

import subprocess
from collections.abc import Sequence


def run_with_subprocess(argv: Sequence[str]) -> int | None:
    try:
        return subprocess.run(list(argv), check=False).returncode
    except OSError:
        return None
