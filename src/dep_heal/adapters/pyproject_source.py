"""Requirements declared in a ``pyproject.toml``'s ``[project].dependencies``."""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from dep_heal.ports import SourceError


class PyprojectSource:
    def __init__(self, pyproject: Path) -> None:
        self._pyproject = pyproject

    def declared(self) -> list[str]:
        try:
            with self._pyproject.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise SourceError(f"{self._pyproject}: {exc}") from exc
        project: object = data.get("project", {})
        deps: object = cast("dict[str, object]", project).get("dependencies", []) if isinstance(project, dict) else []
        if not isinstance(deps, list):
            raise SourceError(f"{self._pyproject}: [project].dependencies is not a list")
        items = cast("list[object]", deps)
        specs = [d for d in items if isinstance(d, str)]
        if len(specs) != len(items):
            raise SourceError(f"{self._pyproject}: [project].dependencies has an entry that is not a string")
        return specs
