"""The use case, under every policy, with in-memory fakes."""
from __future__ import annotations

import pytest

from dependency_repair.domain import InstallPlan, InstallResult, Outcome, RepairPolicy
from dependency_repair.repair import repair
from dependency_repair.testing import FakeConsole, FakeEnvironment, FakeInstaller, FakeSource

MANUAL = "pipx install --editable --force ."


def run(policy, *, source=None, env=None, installer=None, console=None):
    source = source if source is not None else FakeSource(["alpha>=2", "beta"])
    env = env if env is not None else FakeEnvironment({"beta": "1.0"})
    installer = installer if installer is not None else FakeInstaller()
    console = console if console is not None else FakeConsole()
    result = repair(source, env, installer, console, policy=policy, manual_command=MANUAL)
    return result, installer, console


def test_everything_met_touches_nothing_under_every_policy():
    for policy in RepairPolicy:
        result, installer, console = run(policy, env=FakeEnvironment({"alpha": "2.1", "beta": "1"}))
        assert result.outcome is Outcome.UP_TO_DATE and result.satisfied
        assert installer.calls == [] and console.messages == [] and console.questions == []


def test_auto_installs_only_the_unmet_and_says_where():
    result, installer, console = run(RepairPolicy.AUTO)
    assert result.outcome is Outcome.INSTALLED and result.satisfied
    assert installer.calls == [("alpha>=2",)]
    assert "fake-env" in console.messages[0] and "alpha>=2" in console.messages[0]
    assert console.questions == []


def test_a_version_below_the_floor_is_unmet():
    result, installer, _ = run(RepairPolicy.AUTO, env=FakeEnvironment({"alpha": "1.9", "beta": "1"}))
    assert installer.calls == [("alpha>=2",)] and result.unmet == ("alpha>=2",)


def test_prompt_yes_installs_and_the_question_names_the_target():
    result, installer, console = run(RepairPolicy.PROMPT, console=FakeConsole(answer=True))
    assert result.outcome is Outcome.INSTALLED
    assert installer.calls == [("alpha>=2",)]
    assert "alpha>=2" in console.questions[0] and "fake-env" in console.questions[0]


def test_prompt_no_installs_nothing_and_shows_the_manual_command():
    result, installer, console = run(RepairPolicy.PROMPT, console=FakeConsole(answer=False))
    assert result.outcome is Outcome.DECLINED and not result.satisfied
    assert installer.calls == []
    assert MANUAL in console.messages[-1]


def test_prompt_without_a_person_never_asks_and_never_installs():
    result, installer, console = run(RepairPolicy.PROMPT, console=FakeConsole(is_interactive=False))
    assert result.outcome is Outcome.DECLINED and result.detail == "not interactive"
    assert installer.calls == [] and console.questions == []
    assert MANUAL in console.messages[-1]


def test_off_reports_and_installs_nothing_even_when_interactive():
    result, installer, console = run(RepairPolicy.OFF)
    assert result.outcome is Outcome.DISABLED and not result.satisfied
    assert installer.calls == [] and console.questions == []
    assert "alpha>=2" in console.messages[0] and MANUAL in console.messages[0]


@pytest.mark.parametrize("policy", [RepairPolicy.AUTO, RepairPolicy.PROMPT])
def test_no_installer_in_the_environment_is_a_failure_with_the_manual_command(policy):
    result, installer, console = run(policy, env=FakeEnvironment({"beta": "1"}, installer_present=False))
    assert result.outcome is Outcome.INSTALL_FAILED
    assert installer.calls == [] and console.questions == []
    assert MANUAL in console.messages[-1]


def test_a_failed_install_is_reported_with_its_detail_and_not_satisfied():
    result, _, console = run(RepairPolicy.AUTO, installer=FakeInstaller(InstallResult(False, "pip exited 1")))
    assert result.outcome is Outcome.INSTALL_FAILED and not result.satisfied
    assert "pip exited 1" in console.messages[-1] and MANUAL in console.messages[-1]


def test_a_source_with_nothing_to_offer_is_skipped_silently():
    result, installer, console = run(RepairPolicy.AUTO, source=FakeSource(None))
    assert result.outcome is Outcome.SKIPPED and not result.satisfied
    assert installer.calls == [] and console.messages == []


def test_an_unreadable_source_is_a_visible_check_failure_not_a_crash():
    result, installer, console = run(RepairPolicy.AUTO, source=FakeSource(error="boom"))
    assert result.outcome is Outcome.CHECK_FAILED and installer.calls == []
    assert "boom" in console.messages[0]


def test_an_invalid_requirement_string_is_a_visible_check_failure():
    result, installer, console = run(RepairPolicy.AUTO, source=FakeSource(["not a requirement!!"]))
    assert result.outcome is Outcome.CHECK_FAILED and installer.calls == []
    assert "not a requirement" in console.messages[0]


def test_an_empty_declared_list_is_up_to_date():
    result, _, _ = run(RepairPolicy.AUTO, source=FakeSource([]))
    assert result.outcome is Outcome.UP_TO_DATE


PLAN = InstallPlan(("alpha==2.1.0", "gamma==0.3.0"), known=True)  # gamma is something alpha pulls in


def test_the_prompt_lists_every_package_to_be_installed_including_transitive_ones():
    result, installer, console = run(
        RepairPolicy.PROMPT, installer=FakeInstaller(plan_result=PLAN), console=FakeConsole(answer=True)
    )
    (question,) = console.questions
    assert "This will install 2 packages: alpha==2.1.0, gamma==0.3.0 into fake-env" in question
    assert question.endswith("Continue?")
    assert result.outcome is Outcome.INSTALLED and result.packages == PLAN.packages
    assert installer.planned == [("alpha>=2",)] and installer.calls == [("alpha>=2",)]


def test_when_pip_cannot_say_the_prompt_says_the_list_is_incomplete_not_that_it_is_exact():
    _, _, console = run(RepairPolicy.PROMPT, installer=FakeInstaller(plan_result=InstallPlan()))
    assert "alpha>=2 (and anything they depend on)" in console.questions[0]


def test_declining_the_listed_install_installs_nothing_and_keeps_the_list_in_the_result():
    result, installer, _ = run(
        RepairPolicy.PROMPT, installer=FakeInstaller(plan_result=PLAN), console=FakeConsole(answer=False)
    )
    assert result.outcome is Outcome.DECLINED and result.packages == PLAN.packages
    assert installer.calls == []


def test_auto_still_announces_the_full_list_before_installing():
    _, installer, console = run(RepairPolicy.AUTO, installer=FakeInstaller(plan_result=PLAN))
    assert "Installing 2 packages: alpha==2.1.0, gamma==0.3.0 into fake-env" in console.messages[0]
    assert console.questions == [] and installer.calls == [("alpha>=2",)]


def test_off_and_non_interactive_prompt_never_ask_pip_anything():
    for policy, console in ((RepairPolicy.OFF, FakeConsole()), (RepairPolicy.PROMPT, FakeConsole(is_interactive=False))):
        _, installer, _ = run(policy, installer=FakeInstaller(plan_result=PLAN), console=console)
        assert installer.planned == [] and installer.calls == []


def test_a_single_package_is_not_pluralised():
    _, _, console = run(
        RepairPolicy.PROMPT, installer=FakeInstaller(plan_result=InstallPlan(("alpha==2.1.0",), known=True))
    )
    assert "1 package: alpha==2.1.0" in console.questions[0]


def test_extras_default_to_none_and_are_passed_to_the_source_exactly_as_given():
    source = FakeSource(["alpha>=2"], groups={"tracker": ["flask>=3"]})
    heal_args = dict(policy=RepairPolicy.AUTO, manual_command=MANUAL)
    repair(source, FakeEnvironment(), FakeInstaller(), FakeConsole(), **heal_args)
    repair(source, FakeEnvironment(), FakeInstaller(), FakeConsole(), extras=("tracker",), **heal_args)
    assert source.asked_extras == [(), ("tracker",)]


def test_an_extra_adds_its_requirements_to_what_is_installed():
    source = FakeSource(["alpha>=2"], groups={"tracker": ["flask>=3"]})
    installer = FakeInstaller()
    result = repair(source, FakeEnvironment({"alpha": "2.0"}), installer, FakeConsole(),
                    policy=RepairPolicy.AUTO, manual_command=MANUAL, extras=("tracker",))
    assert installer.calls == [("flask>=3",)] and result.outcome is Outcome.INSTALLED


def test_an_unknown_extra_is_a_visible_check_failure():
    installer, console = FakeInstaller(), FakeConsole()
    failed = repair(FakeSource(["alpha>=2"]), FakeEnvironment(), installer, console,
                    policy=RepairPolicy.AUTO, manual_command=MANUAL, extras=("nope",))
    assert failed.outcome is Outcome.CHECK_FAILED and "nope" in console.messages[-1] and installer.calls == []
