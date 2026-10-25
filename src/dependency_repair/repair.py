"""The use case: find what a declared dependency list needs that the environment lacks, and act on the policy."""
from __future__ import annotations

from collections.abc import Sequence

from dependency_repair.domain import (
    InstallPlan,
    InvalidRequirementError,
    Outcome,
    RepairPolicy,
    RepairResult,
    find_unmet,
)
from dependency_repair.ports import Console, Environment, Installer, RequirementSource, SourceError


def _packages_phrase(plan: InstallPlan, unmet: Sequence[str]) -> str:
    """Every package that would be installed, as a person reads it; the declared ones alone when pip could not say."""
    if plan.known and plan.packages:
        noun = "package" if len(plan.packages) == 1 else "packages"
        return f"{len(plan.packages)} {noun}: {', '.join(plan.packages)}"
    return f"{', '.join(unmet)} (and anything they depend on)"


def repair(
    source: RequirementSource,
    environment: Environment,
    installer: Installer,
    console: Console,
    *,
    policy: RepairPolicy,
    manual_command: str,
    extras: Sequence[str] = (),
) -> RepairResult:
    """Install the declared requirements this environment is missing, if the policy allows. Never raises.

    ``extras`` names optional groups to require on top of the base requirements; the caller decides, this module has
    no default group of its own. ``manual_command`` is what a person would type themselves; every outcome that leaves
    requirements unmet shows it. Before anything is installed under ``PROMPT`` the person sees every package it would
    add, transitive ones included, and says yes or no to that whole list.
    """
    try:
        declared = source.declared(extras)
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
    if policy is RepairPolicy.PROMPT and not console.interactive:
        console.say(f"Missing dependencies: {listing}. Not interactive, so nothing was installed. Run: {manual_command}")
        return RepairResult(Outcome.DECLINED, unmet, "not interactive")

    plan = installer.plan(unmet)
    phrase = _packages_phrase(plan, unmet)
    if policy is RepairPolicy.PROMPT:
        if not console.confirm(f"This will install {phrase} into {environment.target()}. Continue?"):
            console.say(f"Nothing installed. Run: {manual_command}")
            return RepairResult(Outcome.DECLINED, unmet, "declined", plan.packages)
    else:
        console.say(f"Installing {phrase} into {environment.target()}")

    done = installer.install(unmet)
    if not done.ok:
        console.say(f"Installing {listing} failed{': ' + done.detail if done.detail else ''}. Run: {manual_command}")
        return RepairResult(Outcome.INSTALL_FAILED, unmet, done.detail, plan.packages)
    return RepairResult(Outcome.INSTALLED, unmet, packages=plan.packages)
