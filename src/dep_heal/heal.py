"""The use case: find what a declared dependency list needs that the environment lacks, and act on the policy."""
from __future__ import annotations

from dep_heal.domain import HealPolicy, HealResult, InvalidRequirementError, Outcome, find_unmet
from dep_heal.ports import Console, Environment, Installer, RequirementSource, SourceError


def heal(
    source: RequirementSource,
    environment: Environment,
    installer: Installer,
    console: Console,
    *,
    policy: HealPolicy,
    manual_command: str,
) -> HealResult:
    """Install the declared requirements this environment is missing, if the policy allows. Never raises.

    ``manual_command`` is what a person would type themselves; every outcome that leaves requirements unmet shows it.
    """
    try:
        declared = source.declared()
    except SourceError as exc:
        console.say(f"Could not read the declared dependencies: {exc}")
        return HealResult(Outcome.CHECK_FAILED, detail=str(exc))
    if declared is None:
        return HealResult(Outcome.SKIPPED)
    try:
        unmet = find_unmet(declared, environment.installed_version)
    except InvalidRequirementError as exc:
        console.say(f"Could not check the declared dependencies: {exc}")
        return HealResult(Outcome.CHECK_FAILED, detail=str(exc))
    if not unmet:
        return HealResult(Outcome.UP_TO_DATE)

    listing = ", ".join(unmet)
    if policy is HealPolicy.OFF:
        console.say(f"Missing dependencies: {listing}. Run: {manual_command}")
        return HealResult(Outcome.DISABLED, unmet)
    if not environment.can_install():
        console.say(f"Missing dependencies: {listing}, and this environment has no installer. Run: {manual_command}")
        return HealResult(Outcome.INSTALL_FAILED, unmet, "no installer in this environment")
    if policy is HealPolicy.PROMPT:
        if not console.interactive:
            console.say(f"Missing dependencies: {listing}. Not interactive, so nothing was installed. Run: {manual_command}")
            return HealResult(Outcome.DECLINED, unmet, "not interactive")
        if not console.confirm(f"Install {listing} into {environment.target()}?"):
            console.say(f"Nothing installed. Run: {manual_command}")
            return HealResult(Outcome.DECLINED, unmet, "declined")
    else:
        console.say(f"Installing missing dependencies into {environment.target()}: {listing}")

    done = installer.install(unmet)
    if not done.ok:
        console.say(f"Installing {listing} failed{': ' + done.detail if done.detail else ''}. Run: {manual_command}")
        return HealResult(Outcome.INSTALL_FAILED, unmet, done.detail)
    return HealResult(Outcome.INSTALLED, unmet)
