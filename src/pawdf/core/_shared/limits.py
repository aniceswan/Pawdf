"""Central, conservative limits for untrusted document inputs.

Every Pawdf feature ultimately calls :func:`ensure_exists`, so these checks also
protect direct users of ``pawdf.core`` rather than only the desktop UI.
Environment variables are available for administrators who deliberately need
larger limits; invalid or non-positive overrides are ignored.
"""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pawdf.core._shared.errors import ConversionError, ResourceLimitError

__all__ = [
    "ResourceLimits",
    "current_limits",
    "preflight_inputs",
    "validate_archive",
    "validate_input_file",
]


_MIB = 1024 * 1024


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class ResourceLimits:
    """Limits applied before a parser receives untrusted bytes."""

    max_input_bytes: int
    max_total_input_bytes: int
    max_pdf_pages: int
    max_image_pixels: int
    max_archive_members: int
    max_archive_uncompressed_bytes: int
    max_archive_ratio: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def current_limits() -> ResourceLimits:
    """Read limits, including supported environment overrides."""

    return ResourceLimits(
        max_input_bytes=_positive_int("PAWDF_MAX_INPUT_MIB", 2048) * _MIB,
        max_total_input_bytes=_positive_int("PAWDF_MAX_TOTAL_INPUT_MIB", 4096) * _MIB,
        max_pdf_pages=_positive_int("PAWDF_MAX_PDF_PAGES", 10_000),
        max_image_pixels=_positive_int("PAWDF_MAX_IMAGE_MEGAPIXELS", 200) * 1_000_000,
        max_archive_members=_positive_int("PAWDF_MAX_ARCHIVE_MEMBERS", 50_000),
        max_archive_uncompressed_bytes=(
            _positive_int("PAWDF_MAX_ARCHIVE_UNCOMPRESSED_MIB", 4096) * _MIB
        ),
        max_archive_ratio=_positive_int("PAWDF_MAX_ARCHIVE_RATIO", 1000),
    )


def _display_bytes(value: int) -> str:
    if value >= 1024**3:
        return f"{value / 1024**3:.1f} GiB"
    return f"{value / 1024**2:.1f} MiB"


def _safe_archive_name(name: str) -> bool:
    if "\x00" in name or name.startswith(("/", "\\")):
        return False
    normalized = PurePosixPath(name.replace("\\", "/"))
    return not any(part == ".." for part in normalized.parts)


def validate_archive(path: str | Path, limits: ResourceLimits | None = None) -> Path:
    """Reject path traversal, archive bombs, and unreasonable Office packages."""

    target = Path(path)
    limits = limits or current_limits()
    try:
        with zipfile.ZipFile(target) as archive:
            members = archive.infolist()
            if len(members) > limits.max_archive_members:
                raise ResourceLimitError(
                    f"'{target.name}' contains {len(members):,} archive entries; "
                    f"the safety limit is {limits.max_archive_members:,}."
                )

            total_uncompressed = 0
            total_compressed = 0
            for info in members:
                if not _safe_archive_name(info.filename):
                    raise ResourceLimitError(
                        f"'{target.name}' contains an unsafe archive path: {info.filename!r}."
                    )
                total_uncompressed += max(0, info.file_size)
                total_compressed += max(0, info.compress_size)
                if total_uncompressed > limits.max_archive_uncompressed_bytes:
                    raise ResourceLimitError(
                        f"'{target.name}' expands beyond "
                        f"{_display_bytes(limits.max_archive_uncompressed_bytes)}, "
                        "so Pawdf stopped before extracting it."
                    )

            if total_uncompressed and total_compressed:
                ratio = total_uncompressed / max(1, total_compressed)
                if ratio > limits.max_archive_ratio:
                    raise ResourceLimitError(
                        f"'{target.name}' has a suspicious compression ratio "
                        f"({ratio:.0f}:1); the safety limit is "
                        f"{limits.max_archive_ratio}:1."
                    )
    except zipfile.BadZipFile as exc:
        # A malformed Office document is a normal conversion failure, not a
        # resource-limit violation. Preserve the public converter contract
        # while keeping archive bombs and unsafe paths as ResourceLimitError.
        raise ConversionError(f"'{target.name}' is not a readable Office/ZIP container.") from exc

    return target


def _validate_pdf_pages(path: Path, limits: ResourceLimits) -> None:
    try:
        import pikepdf
    except ImportError:
        return

    try:
        with pikepdf.open(path, attempt_recovery=False) as pdf:
            pages = len(pdf.pages)
    except pikepdf.PasswordError:
        # Protect/unlock owns the password flow.
        return
    except pikepdf.PdfError:
        # Repair and feature-specific error handling own malformed PDFs.
        return

    if pages > limits.max_pdf_pages:
        raise ResourceLimitError(
            f"'{path.name}' has {pages:,} pages; the safety limit is "
            f"{limits.max_pdf_pages:,}. Set PAWDF_MAX_PDF_PAGES to raise it."
        )


def _validate_image_pixels(path: Path, limits: ResourceLimits) -> None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return

    try:
        with Image.open(path) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError):
        return

    pixels = width * height
    if pixels > limits.max_image_pixels:
        megapixels = pixels / 1_000_000
        allowed = limits.max_image_pixels / 1_000_000
        raise ResourceLimitError(
            f"'{path.name}' is {megapixels:.1f} megapixels; the safety limit is "
            f"{allowed:.0f} megapixels."
        )


def validate_input_file(
    path: str | Path,
    limits: ResourceLimits | None = None,
) -> Path:
    """Validate a regular input file before any feature parses it."""

    target = Path(path).expanduser()
    if not target.is_file():
        raise FileNotFoundError(f"No such file: {target}")

    limits = limits or current_limits()
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise ResourceLimitError(f"Could not inspect '{target}': {exc}") from exc

    if size <= 0:
        raise ResourceLimitError(f"'{target.name}' is empty.")
    if size > limits.max_input_bytes:
        raise ResourceLimitError(
            f"'{target.name}' is {_display_bytes(size)}; the per-file safety "
            f"limit is {_display_bytes(limits.max_input_bytes)}. "
            "Set PAWDF_MAX_INPUT_MIB to raise it."
        )

    suffix = target.suffix.lower()
    if suffix in {".docx", ".xlsx", ".pptx"}:
        validate_archive(target, limits)
    elif suffix == ".pdf":
        _validate_pdf_pages(target, limits)
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        _validate_image_pixels(target, limits)

    return target


def _candidate_paths(value: Any) -> Iterable[Path]:
    if isinstance(value, Path):
        # Output destinations are commonly passed as Path objects but do not
        # exist yet. Only regular files can be inputs worth preflighting.
        try:
            exists = value.expanduser().is_file()
        except (OSError, ValueError):
            exists = False
        if exists:
            yield value.expanduser()
        return
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("[", "{")):
            try:
                decoded = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                decoded = None
            if decoded is not None:
                yield from _candidate_paths(decoded)
                return
        candidate = Path(value).expanduser()
        try:
            exists = candidate.is_file()
        except (OSError, ValueError):
            exists = False
        if exists:
            yield candidate
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _candidate_paths(nested)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            yield from _candidate_paths(nested)


def preflight_inputs(*values: Any, limits: ResourceLimits | None = None) -> list[Path]:
    """Validate every existing input path found in nested arguments.

    Output paths normally do not exist yet and are ignored. JSON path lists
    used by Merge and Images-to-PDF are decoded automatically.
    """

    limits = limits or current_limits()
    unique: list[Path] = []
    seen: set[Path] = set()
    total = 0
    for value in values:
        for candidate in _candidate_paths(value):
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate.absolute()
            if resolved in seen:
                continue
            seen.add(resolved)
            validated = validate_input_file(candidate, limits)
            total += validated.stat().st_size
            if total > limits.max_total_input_bytes:
                raise ResourceLimitError(
                    "The selected files total more than "
                    f"{_display_bytes(limits.max_total_input_bytes)}. "
                    "Process fewer files at once or raise "
                    "PAWDF_MAX_TOTAL_INPUT_MIB."
                )
            unique.append(validated)
    return unique
