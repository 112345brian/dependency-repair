"""The adapters, against real files and streams but never a real install."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from dependency_repair.adapters.editable_source import EditableInstallSource, checkout_from_direct_url, editable_checkout
from dependency_repair.adapters.metadata_environment import MetadataEnvironment
from dependency_repair.adapters.pip_installer import PipInstaller
from dependency_repair.adapters.pyproject_source import PyprojectSource
from dependency_repair.adapters.terminal_console import TerminalConsole
from dependency_repair.ports import SourceError


def write_pyproject(root: Path, body: str) -> Path:
    path = root / "pyproject.toml"
    path.write_text(body, encoding="utf-8")
    return path


def direct_url(url: str, *, editable: bool = True) -> str:
    return json.dumps({"url": url, "dir_info": {"editable": editable}})


class TestPyprojectSource:
    def test_reads_the_dependency_list(self, tmp_path):
        path = write_pyproject(tmp_path, '[project]\nname="x"\ndependencies = ["a>=1", "b"]\n')
        assert PyprojectSource(path).declared() == ["a>=1", "b"]

    def test_no_dependencies_key_is_an_empty_list(self, tmp_path):
        assert PyprojectSource(write_pyproject(tmp_path, '[project]\nname="x"\n')).declared() == []

    @pytest.mark.parametrize("body", ["[project\n", '[project]\ndependencies = "a"\n', "[project]\ndependencies = [1]\n"])
    def test_malformed_files_are_a_source_error_naming_the_file(self, tmp_path, body):
        path = write_pyproject(tmp_path, body)
        with pytest.raises(SourceError, match="pyproject.toml"):
            PyprojectSource(path).declared()

    def test_a_missing_file_is_a_source_error(self, tmp_path):
        with pytest.raises(SourceError):
            PyprojectSource(tmp_path / "pyproject.toml").declared()


class TestCheckoutFromDirectUrl:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (direct_url("file:///C:/home/my%20proj"), Path("C:/home/my proj")),
            (direct_url("file:///home/me/proj"), Path("/home/me/proj")),
        ],
    )
    def test_editable_file_urls_become_paths(self, raw, expected):
        assert checkout_from_direct_url(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, "", "not json", "[]", "{}", direct_url("file:///x", editable=False), direct_url("https://x/y"),
         json.dumps({"url": "file:///x"}), json.dumps({"url": 3, "dir_info": {"editable": True}}),
         json.dumps({"url": "file:///x", "dir_info": {"editable": "yes"}})],
    )
    def test_everything_else_is_none(self, raw):
        assert checkout_from_direct_url(raw) is None


class TestEditableInstallSource:
    def test_declared_comes_from_the_checkout_not_the_installed_metadata(self, tmp_path):
        write_pyproject(tmp_path, '[project]\nname="x"\ndependencies = ["new-dep>=2"]\n')
        source = EditableInstallSource("x", lambda _name: direct_url(tmp_path.as_uri()))
        assert source.declared() == ["new-dep>=2"]

    def test_not_installed_or_not_editable_or_checkout_gone_offers_nothing(self, tmp_path):
        assert EditableInstallSource("x", lambda _n: None).declared() is None
        assert EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri(), editable=False)).declared() is None
        assert EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri())).declared() is None  # no pyproject
        assert editable_checkout("x", lambda _n: direct_url(tmp_path.as_uri())) is None

    def test_a_broken_pyproject_in_the_checkout_is_loud(self, tmp_path):
        write_pyproject(tmp_path, "[project\n")
        with pytest.raises(SourceError):
            EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri())).declared()


class TestMetadataEnvironment:
    def test_reports_installed_and_missing(self):
        env = MetadataEnvironment()
        assert env.installed_version("packaging") is not None
        assert env.installed_version("no-such-distribution-xyz") is None

    def test_target_is_the_interpreter_prefix(self):
        import sys

        assert MetadataEnvironment().target() == sys.prefix


class TestPipInstaller:
    def test_runs_pip_with_the_requirements_and_reports_ok(self):
        seen: list[tuple[str, ...]] = []

        def runner(argv):
            seen.append(tuple(argv))
            return 0

        result = PipInstaller(runner, python="py").install(["a>=1", "b"])
        assert result.ok
        assert seen == [("py", "-m", "pip", "install", "--disable-pip-version-check", "a>=1", "b")]

    def test_nonzero_exit_is_a_failure_with_the_code(self):
        result = PipInstaller(lambda _argv: 3).install(["a"])
        assert not result.ok and "3" in result.detail

    def test_unstartable_pip_is_a_failure(self):
        result = PipInstaller(lambda _argv: None).install(["a"])
        assert not result.ok and "could not be started" in result.detail


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestTerminalConsole:
    def test_a_pipe_is_not_interactive_and_a_tty_is(self):
        assert not TerminalConsole(io.StringIO(), io.StringIO()).interactive
        assert TerminalConsole(Tty(), io.StringIO()).interactive

    @pytest.mark.parametrize("answer, expected", [("y\n", True), ("YES\n", True), ("n\n", False), ("\n", False), ("", False)])
    def test_confirm_defaults_to_no(self, answer, expected):
        err = io.StringIO()
        assert TerminalConsole(Tty(answer), err).confirm("Install?") is expected
        assert "Install?" in err.getvalue() and "[y/N]" in err.getvalue()

    def test_messages_go_to_stderr(self):
        err = io.StringIO()
        TerminalConsole(io.StringIO(), err).say("hello")
        assert err.getvalue() == "hello\n"
