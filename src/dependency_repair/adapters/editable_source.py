"""Requirements for an editable install: read from its checkout, because the venv's own copy is frozen.

An editable install's ``.dist-info`` records the requirements as they were on the day it was installed. A dependency
added to the checkout's ``pyproject.toml`` afterwards is in no installed metadata at all, so the checkout is the only
place that knows about it.
"""
from __future__ import annotations

import importlib.metadata as metadata
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

from dependency_repair.adapters.pyproject_source import PyprojectSource


def checkout_from_direct_url(raw: str | None) -> Path | None:
    """The directory an editable install points at, from its PEP 610 ``direct_url.json`` text; else None."""
    if not raw:
        return None
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    info = cast("dict[str, object]", data)
    url_text = info.get("url")
    dir_info = info.get("dir_info")
    if not isinstance(url_text, str) or not isinstance(dir_info, dict):
        return None
    if cast("dict[str, object]", dir_info).get("editable") is not True:
        return None
    url = urlparse(url_text)
    if url.scheme != "file":
        return None
    path = unquote(url.path)
    if re.match(r"/[A-Za-z]:", path):  # file:///C:/x -> C:/x (a drive letter, not a root-relative path)
        path = path[1:]
    return Path(path)


def _read_direct_url(dist_name: str) -> str | None:
    try:
        return metadata.distribution(dist_name).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None


def editable_checkout(dist_name: str, read_direct_url: Callable[[str], str | None] = _read_direct_url) -> Path | None:
    """The checkout ``dist_name`` is installed editable from, when it still has a ``pyproject.toml``."""
    checkout = checkout_from_direct_url(read_direct_url(dist_name))
    if checkout is None or not (checkout / "pyproject.toml").is_file():
        return None
    return checkout


class EditableInstallSource:
    """Declared requirements of ``dist_name`` when it is an editable install; None for every other kind of install."""

    def __init__(self, dist_name: str, read_direct_url: Callable[[str], str | None] = _read_direct_url) -> None:
        self._dist_name = dist_name
        self._read_direct_url = read_direct_url

    def declared(self, extras: Sequence[str]) -> list[str] | None:
        checkout = editable_checkout(self._dist_name, self._read_direct_url)
        if checkout is None:
            return None
        return PyprojectSource(checkout / "pyproject.toml").declared(extras)
