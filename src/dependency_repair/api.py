"""The composed entry point: repair an editable install with the real adapters. Only a program's entrypoint calls this."""
from __future__ import annotations

from dependency_repair.adapters.editable_source import EditableInstallSource
from dependency_repair.adapters.metadata_environment import MetadataEnvironment
from dependency_repair.adapters.pip_installer import PipInstaller
from dependency_repair.adapters.terminal_console import TerminalConsole
from dependency_repair.domain import RepairPolicy, RepairResult
from dependency_repair.repair import repair
from dependency_repair.ports import CommandRunner, Console


def repair_editable_install(
    dist_name: str,
    *,
    policy: RepairPolicy,
    run_command: CommandRunner,
    manual_command: str,
    console: Console | None = None,
) -> RepairResult:
    """Make the running environment meet the requirements ``dist_name``'s checkout declares, per ``policy``."""
    return repair(
        EditableInstallSource(dist_name),
        MetadataEnvironment(),
        PipInstaller(run_command),
        console if console is not None else TerminalConsole(),
        policy=policy,
        manual_command=manual_command,
    )
