"""The use case: find what a declared dependency list needs that the environment lacks, and act on the policy."""
from __future__ import annotations

from dependency_repair.domain import RepairPolicy, RepairResult, InvalidRequirementError, Outcome, find_unmet
from dependency_repair.ports import Console, Environment, Installer, RequirementSource, SourceError


def repair(
    source: RequirementSource,
    environment: Environment,
    installer: Installer,
    console: Console,
    *,
    policy: RepairPolicy,
    manual_command: str,
) -> RepairResult:
    """Install the declared requirements this environment is missing, if the policy allows. Never raises.

    ``manual_command`` is what a person would type themselves; every outcome that leaves requirements unmet shows it.
    """
    try:
        declared = source.declared()
    except SourceError as exc:
        console.say(f"Could not read the declared dependencies: {exc}")
        return RepairResult(Outcome.CHECK_FAILED, detail=str(exc))
    if declared is None:
        return RepairResult(Outcome.SKIPPED)
    try:
        unmet = find_unmet(declared, environment.installed_version)
    except InvalidRequirementError as exc:
        console.say(f"Could not check the declared dependencies: {exc}")
        return RepairResult(Outcome.CHECK_FAILED, detail=str(exc))
    if not unmet:
        return RepairResult(Outcome.UP_TO_DATE)

    listing = ", ".join(unmet)
    if policy is RepairPolicy.OFF:
        console.say(f"Missing dependencies: {listing}. Run: {manual_command}")
        return RepairResult(Outcome.DISABLED, unmet)
    if not environment.can_install():
        console.say(f"Missing dependencies: {listing}, and this environment has no installer. Run: {manual_command}")
        return RepairResult(Outcome.INSTALL_FAILED, unmet, "no installer in this environment")
    if policy is RepairPolicy.PROMPT:
        if not console.interactive:
            console.say(f"Missing dependencies: {listing}. Not interactive, so nothing was installed. Run: {manual_command}")
            return RepairResult(Outcome.DECLINED, unmet, "not interactive")
        if not console.confirm(f"Install {listing} into {environment.target()}?"):
            console.say(f"Nothing installed. Run: {manual_command}")
            return RepairResult(Outcome.DECLINED, unmet, "declined")
    else:
        console.say(f"Installing missing dependencies into {environment.target()}: {listing}")

    done = installer.install(unmet)
    if not done.ok:
        console.say(f"Installing {listing} failed{': ' + done.detail if done.detail else ''}. Run: {manual_command}")
        return RepairResult(Outcome.INSTALL_FAILED, unmet, done.detail)
    return RepairResult(Outcome.INSTALLED, unmet)
