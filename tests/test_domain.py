from __future__ import annotations

import pytest

from dep_heal.domain import HealPolicy, InvalidRequirementError, find_unmet, parse_policy


@pytest.mark.parametrize(
    "raw, expected",
    [("auto", HealPolicy.AUTO), (" PROMPT ", HealPolicy.PROMPT), ("Off", HealPolicy.OFF),
     (None, None), ("", None), ("yes", None), ("always", None)],
)
def test_parse_policy(raw, expected):
    assert parse_policy(raw) is expected


def versions(table):
    return lambda name: table.get(name)


def test_missing_and_too_old_are_unmet_and_met_are_not():
    specs = ["a>=2", "b", "c (>=1,<2)", "d>=1"]
    assert find_unmet(specs, versions({"a": "1.0", "c": "2.0", "d": "1.5"})) == ("a>=2", "b", "c (>=1,<2)")


def test_a_prerelease_satisfies_a_range():
    assert find_unmet(["a>=2"], versions({"a": "2.1rc1"})) == ()


def test_four_part_versions_compare_as_versions_not_text():
    assert find_unmet(["a>=4.41"], versions({"a": "4.9"})) == ("a>=4.41",)
    assert find_unmet(["a>=4.9"], versions({"a": "4.41"})) == ()


def test_a_false_marker_is_not_unmet():
    assert find_unmet(['a; sys_platform == "plan9"'], versions({})) == ()


def test_a_true_marker_still_requires_the_package():
    assert find_unmet(['a; python_version >= "3"'], versions({})) == ('a; python_version >= "3"',)


def test_invalid_requirement_raises_with_the_text():
    with pytest.raises(InvalidRequirementError, match="nope!!"):
        find_unmet(["nope!!"], versions({}))
