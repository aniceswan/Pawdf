"""Path validation helpers shared by every feature package."""

from __future__ import annotations

from pathlib import Path

from pawdf.core._shared.limits import validate_input_file


def ensure_exists(path: str | Path) -> Path:
    """Return a validated regular input file."""

    return validate_input_file(path)


def ensure_parent_dir(path: str | Path) -> Path:
    """Return ``path`` as a Path, creating its parent directory if needed."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
