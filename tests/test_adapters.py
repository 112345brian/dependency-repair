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
        assert PyprojectSource(path).declared(()) == ["a>=1", "b"]

    def test_no_dependencies_key_is_an_empty_list(self, tmp_path):
        assert PyprojectSource(write_pyproject(tmp_path, '[project]\nname="x"\n')).declared(()) == []

    @pytest.mark.parametrize("body", ["[project\n", '[project]\ndependencies = "a"\n', "[project]\ndependencies = [1]\n"])
    def test_malformed_files_are_a_source_error_naming_the_file(self, tmp_path, body):
        path = write_pyproject(tmp_path, body)
        with pytest.raises(SourceError, match="pyproject.toml"):
            PyprojectSource(path).declared(())

    def test_a_missing_file_is_a_source_error(self, tmp_path):
        with pytest.raises(SourceError):
            PyprojectSource(tmp_path / "pyproject.toml").declared(())


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
        assert source.declared(()) == ["new-dep>=2"]

    def test_not_installed_or_not_editable_or_checkout_gone_offers_nothing(self, tmp_path):
        assert EditableInstallSource("x", lambda _n: None).declared(()) is None
        assert EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri(), editable=False)).declared(()) is None
        assert EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri())).declared(()) is None  # no pyproject
        assert editable_checkout("x", lambda _n: direct_url(tmp_path.as_uri())) is None

    def test_a_broken_pyproject_in_the_checkout_is_loud(self, tmp_path):
        write_pyproject(tmp_path, "[project\n")
        with pytest.raises(SourceError):
            EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri())).declared(())


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


class TestPyprojectExtras:
    BODY = (
        '[project]\nname = "x"\ndependencies = ["base>=1"]\n'
        '[project.optional-dependencies]\ntracker = ["flask>=3", "base>=1"]\nscoring = ["numpy"]\n'
    )

    def test_no_extras_is_the_base_list_only(self, tmp_path):
        assert PyprojectSource(write_pyproject(tmp_path, self.BODY)).declared(()) == ["base>=1"]

    def test_named_extras_are_added_in_order_without_duplicates(self, tmp_path):
        source = PyprojectSource(write_pyproject(tmp_path, self.BODY))
        assert source.declared(("tracker", "scoring")) == ["base>=1", "flask>=3", "numpy"]

    def test_an_undeclared_extra_is_a_loud_error_naming_it(self, tmp_path):
        source = PyprojectSource(write_pyproject(tmp_path, self.BODY))
        with pytest.raises(SourceError, match="nope"):
            source.declared(("nope",))

    def test_an_undeclared_extra_with_no_groups_table_at_all_is_still_an_error(self, tmp_path):
        source = PyprojectSource(write_pyproject(tmp_path, '[project]\nname = "x"\ndependencies = []\n'))
        with pytest.raises(SourceError, match="tracker"):
            source.declared(("tracker",))

    def test_the_editable_source_passes_extras_through(self, tmp_path):
        write_pyproject(tmp_path, self.BODY)
        source = EditableInstallSource("x", lambda _n: direct_url(tmp_path.as_uri()))
        assert source.declared(("scoring",)) == ["base>=1", "numpy"]


def report(*pairs):
    return json.dumps({"version": "1", "install": [{"metadata": {"name": n, "version": v}} for n, v in pairs]})


def pip_that_writes(content, code=0, seen=None):
    """A command runner that behaves like pip: writes ``content`` to the --report path and exits ``code``."""

    def runner(argv):
        if seen is not None:
            seen.append(tuple(argv))
        if content is not None and "--report" in argv:
            Path(argv[list(argv).index("--report") + 1]).write_text(content, encoding="utf-8")
        return code

    return runner


class TestPipPlan:
    def test_lists_every_package_pip_would_install_transitive_ones_included(self):
        seen: list[tuple[str, ...]] = []
        runner = pip_that_writes(report(("flask", "3.0.0"), ("werkzeug", "3.0.1")), seen=seen)
        plan = PipInstaller(runner, python="py").plan(["flask>=3"])
        assert plan.known and plan.packages == ("flask==3.0.0", "werkzeug==3.0.1")
        (argv,) = seen
        assert argv[:7] == ("py", "-m", "pip", "install", "--disable-pip-version-check", "--dry-run", "--quiet")
        assert argv[7] == "--report" and argv[-1] == "flask>=3"

    def test_non_ascii_metadata_survives_because_the_report_is_read_as_utf_8(self):
        plan = PipInstaller(pip_that_writes(report(("pkg-\u00f6", "1.0")))).plan(["x"])
        assert plan.packages == ("pkg-\u00f6==1.0",)

    @pytest.mark.parametrize(
        "runner",
        [pip_that_writes(report(("a", "1")), code=1), lambda _argv: None, pip_that_writes(None), pip_that_writes("not json"),
         pip_that_writes("[]"), pip_that_writes("{}"), pip_that_writes(json.dumps({"install": [{"metadata": {"name": "a"}}]})),
         pip_that_writes(json.dumps({"install": ["a"]}))],
    )
    def test_anything_unusable_is_an_unknown_plan_not_an_error(self, runner):
        plan = PipInstaller(runner).plan(["a"])
        assert not plan.known and plan.packages == ()

    def test_an_empty_install_list_is_a_known_empty_plan(self):
        plan = PipInstaller(pip_that_writes(report())).plan(["a"])
        assert plan.known and plan.packages == ()

    def test_the_temporary_report_is_removed(self):
        seen: list[tuple[str, ...]] = []
        PipInstaller(pip_that_writes(report(("a", "1")), seen=seen)).plan(["a"])
        path = Path(seen[0][seen[0].index("--report") + 1])
        assert not path.exists() and not path.parent.exists()
