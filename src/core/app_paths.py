"""Application-root paths, independent of the process working directory."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved locations; resolving paths never creates directories."""

    root: Path
    config_dir: Path
    testcase_dir: Path
    logs_dir: Path
    docs_dir: Path

    @classmethod
    def resolve(cls, app_root: str | os.PathLike[str] | None = None) -> AppPaths:
        """Choose explicit root, DOIP_APP_DIR, frozen executable, then source.

        Explicit and environment roots must be absolute: accepting relative
        roots would make launching from another working directory ambiguous.
        """
        candidate = app_root
        if candidate is None:
            candidate = os.environ.get("DOIP_APP_DIR") or None
        if candidate is None:
            if getattr(sys, "frozen", False):
                candidate = Path(sys.executable).parent
            else:
                candidate = Path(__file__).resolve().parents[2]
        root = Path(candidate)
        if not root.is_absolute():
            raise ValueError("Application root must be an absolute path")
        root = root.resolve()
        return cls(
            root=root,
            config_dir=root / "config",
            testcase_dir=root / "testcase",
            logs_dir=root / "logs",
            docs_dir=root / "docs",
        )
