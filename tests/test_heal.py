"""The use case, under every policy, with in-memory fakes."""
from __future__ import annotations

import pytest

from dep_heal.domain import HealPolicy, InstallResult, Outcome
from dep_heal.heal import heal
from dep_heal.testing import FakeConsole, FakeEnvironment, FakeInstaller, FakeSource

MANUAL = "pipx install --editable --force ."


def run(policy, *, source=None, env=None, installer=None, console=None):
    source = source if source is not None else FakeSource(["alpha>=2", "beta"])
    env = env if env is not None else FakeEnvironment({"beta": "1.0"})
    installer = installer if installer is not None else FakeInstaller()
    console = console if console is not None else FakeConsole()
    result = heal(source, env, installer, console, policy=policy, manual_command=MANUAL)
    return result, installer, console


def test_everything_met_touches_nothing_under_every_policy():
    for policy in HealPolicy:
        result, installer, console = run(policy, env=FakeEnvironment({"alpha": "2.1", "beta": "1"}))
        assert result.outcome is Outcome.UP_TO_DATE and result.satisfied
        assert installer.calls == [] and console.messages == [] and console.questions == []


def test_auto_installs_only_the_unmet_and_says_where():
    result, installer, console = run(HealPolicy.AUTO)
    assert result.outcome is Outcome.INSTALLED and result.satisfied
    assert installer.calls == [("alpha>=2",)]
    assert "fake-env" in console.messages[0] and "alpha>=2" in console.messages[0]
    assert console.questions == []


def test_a_version_below_the_floor_is_unmet():
    result, installer, _ = run(HealPolicy.AUTO, env=FakeEnvironment({"alpha": "1.9", "beta": "1"}))
    assert installer.calls == [("alpha>=2",)] and result.unmet == ("alpha>=2",)


def test_prompt_yes_installs_and_the_question_names_the_target():
    result, installer, console = run(HealPolicy.PROMPT, console=FakeConsole(answer=True))
    assert result.outcome is Outcome.INSTALLED
    assert installer.calls == [("alpha>=2",)]
    assert "alpha>=2" in console.questions[0] and "fake-env" in console.questions[0]


def test_prompt_no_installs_nothing_and_shows_the_manual_command():
    result, installer, console = run(HealPolicy.PROMPT, console=FakeConsole(answer=False))
    assert result.outcome is Outcome.DECLINED and not result.satisfied
    assert installer.calls == []
    assert MANUAL in console.messages[-1]


def test_prompt_without_a_person_never_asks_and_never_installs():
    result, installer, console = run(HealPolicy.PROMPT, console=FakeConsole(is_interactive=False))
    assert result.outcome is Outcome.DECLINED and result.detail == "not interactive"
    assert installer.calls == [] and console.questions == []
    assert MANUAL in console.messages[-1]


def test_off_reports_and_installs_nothing_even_when_interactive():
    result, installer, console = run(HealPolicy.OFF)
    assert result.outcome is Outcome.DISABLED and not result.satisfied
    assert installer.calls == [] and console.questions == []
    assert "alpha>=2" in console.messages[0] and MANUAL in console.messages[0]


@pytest.mark.parametrize("policy", [HealPolicy.AUTO, HealPolicy.PROMPT])
def test_no_installer_in_the_environment_is_a_failure_with_the_manual_command(policy):
    result, installer, console = run(policy, env=FakeEnvironment({"beta": "1"}, installer_present=False))
    assert result.outcome is Outcome.INSTALL_FAILED
    assert installer.calls == [] and console.questions == []
    assert MANUAL in console.messages[-1]


def test_a_failed_install_is_reported_with_its_detail_and_not_satisfied():
    result, _, console = run(HealPolicy.AUTO, installer=FakeInstaller(InstallResult(False, "pip exited 1")))
    assert result.outcome is Outcome.INSTALL_FAILED and not result.satisfied
    assert "pip exited 1" in console.messages[-1] and MANUAL in console.messages[-1]


def test_a_source_with_nothing_to_offer_is_skipped_silently():
    result, installer, console = run(HealPolicy.AUTO, source=FakeSource(None))
    assert result.outcome is Outcome.SKIPPED and not result.satisfied
    assert installer.calls == [] and console.messages == []


def test_an_unreadable_source_is_a_visible_check_failure_not_a_crash():
    result, installer, console = run(HealPolicy.AUTO, source=FakeSource(error="boom"))
    assert result.outcome is Outcome.CHECK_FAILED and installer.calls == []
    assert "boom" in console.messages[0]


def test_an_invalid_requirement_string_is_a_visible_check_failure():
    result, installer, console = run(HealPolicy.AUTO, source=FakeSource(["not a requirement!!"]))
    assert result.outcome is Outcome.CHECK_FAILED and installer.calls == []
    assert "not a requirement" in console.messages[0]


def test_an_empty_declared_list_is_up_to_date():
    result, _, _ = run(HealPolicy.AUTO, source=FakeSource([]))
    assert result.outcome is Outcome.UP_TO_DATE
