"""The composed entry point: heal an editable install with the real adapters. Only a program's entrypoint calls this."""
from __future__ import annotations

from dep_heal.adapters.editable_source import EditableInstallSource
from dep_heal.adapters.metadata_environment import MetadataEnvironment
from dep_heal.adapters.pip_installer import PipInstaller
from dep_heal.adapters.terminal_console import TerminalConsole
from dep_heal.domain import HealPolicy, HealResult
from dep_heal.heal import heal
from dep_heal.ports import CommandRunner, Console


def heal_editable_install(
    dist_name: str,
    *,
    policy: HealPolicy,
    run_command: CommandRunner,
    manual_command: str,
    console: Console | None = None,
) -> HealResult:
    """Make the running environment meet the requirements ``dist_name``'s checkout declares, per ``policy``."""
    return heal(
        EditableInstallSource(dist_name),
        MetadataEnvironment(),
        PipInstaller(run_command),
        console if console is not None else TerminalConsole(),
        policy=policy,
        manual_command=manual_command,
    )
