"""The running interpreter's environment, via ``importlib.metadata``."""
from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import sys


class MetadataEnvironment:
    def installed_version(self, name: str) -> str | None:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return None

    def can_install(self) -> bool:
        return importlib.util.find_spec("pip") is not None

    def target(self) -> str:
        return sys.prefix
