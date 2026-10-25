"""Requirements declared in a ``pyproject.toml``: ``[project].dependencies`` plus any named optional-dependency groups."""
from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from dependency_repair.ports import SourceError


class PyprojectSource:
    def __init__(self, pyproject: Path) -> None:
        self._pyproject = pyproject

    def declared(self, extras: Sequence[str]) -> list[str]:
        try:
            with self._pyproject.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise SourceError(f"{self._pyproject}: {exc}") from exc
        project = self._table(data.get("project", {}), "[project]")
        specs = self._strings(project.get("dependencies", []), "[project].dependencies")
        if extras:
            groups = self._table(project.get("optional-dependencies", {}), "[project.optional-dependencies]")
            for extra in extras:
                if extra not in groups:
                    raise SourceError(f"{self._pyproject}: no [project.optional-dependencies].{extra}")
                specs += self._strings(groups[extra], f"[project.optional-dependencies].{extra}")
        return list(dict.fromkeys(specs))

    def _table(self, value: object, where: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise SourceError(f"{self._pyproject}: {where} is not a table")
        return cast("dict[str, object]", value)

    def _strings(self, value: object, where: str) -> list[str]:
        if not isinstance(value, list):
            raise SourceError(f"{self._pyproject}: {where} is not a list")
        items = cast("list[object]", value)
        specs = [item for item in items if isinstance(item, str)]
        if len(specs) != len(items):
            raise SourceError(f"{self._pyproject}: {where} has an entry that is not a string")
        return specs
