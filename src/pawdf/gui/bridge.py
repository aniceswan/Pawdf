"""The Python side of the UI: every call the page can make, and every event
it can receive.

Exposed to JavaScript over a QWebChannel. Two rules hold everywhere below:

* Anything that touches a file goes through here. The page never gets
  filesystem access of its own - it asks for a native dialog, or the user
  drags something in (see dnd.py).
* Anything that could take more than a few milliseconds runs on a worker
  thread and answers with a signal, never a return value. A blocking slot
  would freeze the Qt event loop and the Chromium renderer with it.

Results cross the channel as JSON strings rather than as structured types:
QWebChannel's automatic conversion is fussy about nested containers, and one
`JSON.parse` on the far side is easier to reason about than debugging why a
list of tuples arrived as something unexpected.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import shutil
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QStandardPaths, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from pawdf.core import registry
from pawdf.core._shared import PawdfError
from pawdf.core._shared.limits import preflight_inputs
from pawdf.gui.diagnostics import (
    clear_logs,
    create_diagnostic_bundle,
    diagnostic_info,
)
from pawdf.gui.workers import JobRunner

__all__ = ["FEATURE_CHANNELS", "Bridge"]

THUMBNAIL_DPI = 70
logger = logging.getLogger("pawdf.bridge")

#: Overrides the Downloads folder as the destination for every result.
OUTPUT_DIR_ENV = "PAWDF_OUTPUT_DIR"

FEATURE_CHANNELS: dict[str, tuple[str, str, str]] = {
    "split": ("runSplit", "splitFinished", "splitFailed"),
    "merge": ("runMerge", "mergeFinished", "mergeFailed"),
    "organize": ("runOrganize", "organizeFinished", "organizeFailed"),
    "compress": ("runCompress", "compressFinished", "compressFailed"),
    "ocr": ("runOcr", "ocrFinished", "ocrFailed"),
    "rasterize": ("runRasterize", "rasterizeFinished", "rasterizeFailed"),
    "imagepdf": ("runImagePdf", "imagepdfFinished", "imagepdfFailed"),
    "rotate": ("runRotate", "rotateFinished", "rotateFailed"),
    "crop": ("runCrop", "cropFinished", "cropFailed"),
    "repair": ("runRepair", "repairFinished", "repairFailed"),
    "protect": ("runProtect", "protectFinished", "protectFailed"),
    "unlock": ("runUnlock", "unlockFinished", "unlockFailed"),
    "watermark": ("runWatermark", "watermarkFinished", "watermarkFailed"),
    "sign": ("runSign", "signFinished", "signFailed"),
    "pagenumbers": (
        "runPageNumbers",
        "pagenumbersFinished",
        "pagenumbersFailed",
    ),
    "pdf_to_docx": (
        "runPdfToWord",
        "pdfToWordFinished",
        "pdfToWordFailed",
    ),
    "docx_to_pdf": (
        "runWordToPdf",
        "wordToPdfFinished",
        "wordToPdfFailed",
    ),
    "forms": ("runFillForm", "formsFinished", "formsFailed"),
    "annotate": ("runAnnotate", "annotateFinished", "annotateFailed"),
    "pdf_to_markdown": (
        "runMarkdown",
        "markdownFinished",
        "markdownFailed",
    ),
    "xlsx_to_pdf": (
        "runXlsxToPdf",
        "xlsxToPdfFinished",
        "xlsxToPdfFailed",
    ),
    "pptx_to_pdf": (
        "runPptxToPdf",
        "pptxToPdfFinished",
        "pptxToPdfFailed",
    ),
}

# Filters for the native dialogs, keyed the way the page refers to them.
# "any" is what the page's Add-files button uses: the user chooses the file
# first and the tool second, so the dialog can't know yet which of these it
# will turn out to be.
_IMAGE_GLOBS = "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"
_OFFICE_GLOBS = "*.docx *.xlsx *.pptx"

FILE_FILTERS = {
    "any": (
        f"All supported files (*.pdf {_OFFICE_GLOBS} {_IMAGE_GLOBS});;"
        "PDF files (*.pdf);;"
        f"Office documents ({_OFFICE_GLOBS});;"
        f"Images ({_IMAGE_GLOBS});;"
        "All files (*)"
    ),
    "pdf": "PDF files (*.pdf)",
    "docx": "Word documents (*.docx)",
    "xlsx": "Excel workbooks (*.xlsx)",
    "pptx": "PowerPoint presentations (*.pptx)",
    "image": f"Images ({_IMAGE_GLOBS})",
}


def _message_for(exc: Exception) -> str:
    """Errors core/ raised on purpose already read well; anything else is a
    bug and is labelled as such rather than dressed up as normal.
    """
    if isinstance(exc, PawdfError):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return f"That file no longer exists: {exc}"
    return f"Unexpected error: {type(exc).__name__}: {exc}"


def _fallback_result_payload(result: Any) -> dict[str, Any]:
    """Preserve a successful write when optional UI shaping fails."""

    output_path = getattr(result, "output_path", None)
    if output_path is not None:
        return {
            "output": str(output_path),
            "detailsUnavailable": True,
        }
    if isinstance(result, (list, tuple)):
        return {
            "outputs": [str(item) for item in result],
            "count": len(result),
            "detailsUnavailable": True,
        }
    return {
        "output": str(result),
        "detailsUnavailable": True,
    }


class Bridge(QObject):
    """Every slot the page can call, and every signal it can listen for."""

    # One pair per operation: the page enables its button again on either.
    splitFinished = Signal(str)
    splitFailed = Signal(str)
    mergeFinished = Signal(str)
    mergeFailed = Signal(str)
    organizeFinished = Signal(str)
    organizeFailed = Signal(str)
    rasterizeFinished = Signal(str)
    rasterizeFailed = Signal(str)
    imagepdfFinished = Signal(str)
    imagepdfFailed = Signal(str)
    pdfToWordFinished = Signal(str)
    pdfToWordFailed = Signal(str)
    wordToPdfFinished = Signal(str)
    wordToPdfFailed = Signal(str)
    compressFinished = Signal(str)
    compressFailed = Signal(str)
    rotateFinished = Signal(str)
    rotateFailed = Signal(str)
    cropFinished = Signal(str)
    cropFailed = Signal(str)
    repairFinished = Signal(str)
    repairFailed = Signal(str)
    protectFinished = Signal(str)
    protectFailed = Signal(str)
    unlockFinished = Signal(str)
    unlockFailed = Signal(str)
    watermarkFinished = Signal(str)
    watermarkFailed = Signal(str)
    signFinished = Signal(str)
    signFailed = Signal(str)
    pagenumbersFinished = Signal(str)
    pagenumbersFailed = Signal(str)
    markdownFinished = Signal(str)
    markdownFailed = Signal(str)
    xlsxToPdfFinished = Signal(str)
    xlsxToPdfFailed = Signal(str)
    pptxToPdfFinished = Signal(str)
    pptxToPdfFailed = Signal(str)
    ocrFinished = Signal(str)
    ocrFailed = Signal(str)
    formsFinished = Signal(str)
    formsFailed = Signal(str)
    annotateFinished = Signal(str)
    annotateFailed = Signal(str)
    ghostscriptFinished = Signal(str)
    ghostscriptFailed = Signal(str)
    jobCountChanged = Signal(int)
    allJobsFinished = Signal()

    # Thumbnails answer one page at a time so the grid can fill in progressively.
    thumbnailReady = Signal(str)

    # Native drag-and-drop, which the page cannot observe on its own.
    filesDropped = Signal(str)
    dragStateChanged = Signal(bool)

    def __init__(self, parent_widget: QWidget | None = None):
        super().__init__()
        self._parent_widget = parent_widget
        self._jobs = JobRunner(on_change=self._on_job_count)
        self._output_lock = threading.Lock()
        self._reserved_outputs: set[Path] = set()

    # ---------------------------------------------------------------- meta --

    @Slot(result=str)
    def features(self) -> str:
        """The tool list and the categories that group them, straight from
        core/registry.py.

        The page builds both rings from this, so adding a tool is a change to
        the registry rather than to the markup. The resolved hue is sent
        alongside each feature so the page never has to know that tools
        normally inherit their category's colour.
        """
        return json.dumps(
            {
                "categories": [asdict(c) for c in registry.CATEGORIES],
                "features": [{**asdict(f), "hue": registry.hue_of(f)} for f in registry.FEATURES],
            }
        )

    @Slot(result=str)
    def appInfo(self) -> str:
        from pawdf import __version__

        return json.dumps({"version": __version__})

    @property
    def active_jobs(self) -> int:
        """Number of writes that still own a worker thread."""

        return self._jobs.total

    def _on_job_count(self, count: int) -> None:
        self.jobCountChanged.emit(count)
        if count == 0:
            self.allJobsFinished.emit()

    @Slot(result=int)
    def activeJobs(self) -> int:
        return self.active_jobs

    @Slot(str, result=str)
    def existingFiles(self, paths_json: str) -> str:
        """Return only regular files that still exist, preserving order."""

        try:
            paths = json.loads(paths_json)
        except (TypeError, json.JSONDecodeError):
            return "[]"
        if not isinstance(paths, list):
            return "[]"

        existing: list[str] = []
        for value in paths:
            if not isinstance(value, str):
                continue
            candidate = Path(value)
            try:
                if candidate.is_file():
                    existing.append(str(candidate))
            except (OSError, ValueError):
                continue
        return json.dumps(existing)

    @Slot(result=str)
    def diagnosticInfo(self) -> str:
        return json.dumps(diagnostic_info())

    @Slot(result=str)
    def exportDiagnostics(self) -> str:
        try:
            return str(create_diagnostic_bundle(self.download_dir()))
        except Exception as exc:  # noqa: BLE001 - returned as a user-facing error
            raise PawdfError(f"Could not create diagnostics: {exc}") from exc

    @Slot()
    def clearDiagnosticLogs(self) -> None:
        clear_logs()

    # ------------------------------------------------------------- dialogs --

    @Slot(str, str, result=str)
    def pickOpenFile(self, title: str, kind: str) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self._parent_widget, title, "", FILE_FILTERS.get(kind, "All files (*)")
        )
        return path

    @Slot(str, str, result="QStringList")
    def pickOpenFiles(self, title: str, kind: str) -> list[str]:
        paths, _ = QFileDialog.getOpenFileNames(
            self._parent_widget, title, "", FILE_FILTERS.get(kind, "All files (*)")
        )
        return paths

    # ------------------------------------------------------------- output --
    #
    # Operations first produce collision-safe results without interrupting the
    # workflow with a dialog. The result shelf can then Save one/all outputs or
    # Continue an output directly into another compatible tool.

    @staticmethod
    def download_dir() -> Path:
        """Where results are written, created if it doesn't exist.

        Normally the user's Downloads folder. QStandardPaths honours the XDG
        user-dirs config on Linux, so this is the localised folder ("Unduhan",
        "Téléchargements", ...) rather than a hard-coded English name.

        `PAWDF_OUTPUT_DIR` overrides it. That exists so the test suite doesn't
        scatter files through the developer's real Downloads folder, but it is
        a documented escape hatch for anyone who wants results somewhere else.
        """
        override = os.environ.get(OUTPUT_DIR_ENV)
        if override:
            folder = Path(override).expanduser()
        else:
            raw = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
            folder = Path(raw) if raw else Path.home() / "Downloads"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def _unique(path: Path) -> Path:
        """`path`, or the first " (n)" variant of it that doesn't exist yet."""
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _reserve_unique(self, path: Path) -> Path:
        """Reserve a collision-safe path before its worker starts writing."""

        with self._output_lock:
            candidate = path
            counter = 2
            while candidate.exists() or candidate in self._reserved_outputs:
                candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
                counter += 1
            self._reserved_outputs.add(candidate)
            return candidate

    def _claimed_outputs(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> set[Path]:
        candidates = [value for value in (*args, *kwargs.values()) if isinstance(value, Path)]
        with self._output_lock:
            return {value for value in candidates if value in self._reserved_outputs}

    def _release_outputs(self, paths: set[Path]) -> None:
        if not paths:
            return
        with self._output_lock:
            self._reserved_outputs.difference_update(paths)

    def _out_file(self, source: str, suffix: str, *, tag: str = "") -> Path:
        """A path reserved until the corresponding worker completes."""

        stem = Path(source).stem
        name = f"{stem}{tag}{suffix}" if stem else f"pawdf{tag}{suffix}"
        return self._reserve_unique(self.download_dir() / name)

    def _out_dir(self, source: str, tag: str) -> Path:
        """A free *folder* in Downloads, for operations that write many files."""
        stem = Path(source).stem or "pawdf"
        base = self.download_dir() / f"{stem}{tag}"
        candidate, counter = base, 2
        while candidate.exists():
            candidate = base.with_name(f"{base.name} ({counter})")
            counter += 1
        candidate.mkdir(parents=True)
        return candidate

    @Slot(str)
    def revealPath(self, path: str) -> None:
        """Open the containing folder in the system file manager."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        target = Path(path)
        folder = target.parent if target.is_file() else target
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @Slot(str, result=str)
    def saveOutput(self, source_path: str) -> str:
        """Copy one generated result to a location chosen by the user.

        Operations still write collision-safe working results first, which
        means a result can be continued into another Pawdf tool immediately.
        This slot adds an explicit Save action without forcing a destination
        dialog before every operation.
        """
        source = Path(source_path)
        if not source.is_file():
            return ""

        suffix = source.suffix.lower()
        file_filter = (
            f"{suffix.removeprefix('.').upper()} files (*{suffix});;All files (*)"
            if suffix
            else "All files (*)"
        )
        suggested = self.download_dir() / source.name
        chosen, _ = QFileDialog.getSaveFileName(
            self._parent_widget,
            "Save result",
            str(suggested),
            file_filter,
        )
        if not chosen:
            return ""

        destination = Path(chosen).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
        except OSError as exc:
            raise PawdfError(f"Could not save '{source.name}': {exc}") from exc
        return str(destination)

    @Slot(str, result=str)
    def saveOutputs(self, paths_json: str) -> str:
        """Copy several generated results into one chosen folder."""
        try:
            sources = [Path(path) for path in json.loads(paths_json)]
        except (TypeError, json.JSONDecodeError):
            return "[]"
        sources = [source for source in sources if source.is_file()]
        if not sources:
            return "[]"

        chosen = QFileDialog.getExistingDirectory(
            self._parent_widget,
            "Save all results",
            str(self.download_dir()),
        )
        if not chosen:
            return "[]"

        folder = Path(chosen).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        try:
            for source in sources:
                direct = folder / source.name
                if source.resolve() == direct.resolve():
                    destination = direct
                else:
                    destination = self._unique(direct)
                    shutil.copy2(source, destination)
                saved.append(str(destination))
        except OSError as exc:
            raise PawdfError(f"Could not save all results: {exc}") from exc
        return json.dumps(saved)

    # ---------------------------------------------------------- operations --

    def _dispatch(
        self,
        finished: Signal,
        failed: Signal,
        fn: Any,
        *args: Any,
        shape: Any = None,
        **kwargs: Any,
    ) -> None:
        """Validate inputs, run ``fn`` in the background, and report JSON."""

        operation = getattr(fn, "__name__", type(fn).__name__)
        claimed_outputs = self._claimed_outputs(args, kwargs)
        try:
            preflight_inputs(args, kwargs)
        except Exception as exc:  # noqa: BLE001 - normalized for the UI
            self._release_outputs(claimed_outputs)
            logger.warning(
                "Preflight rejected operation=%s error=%s",
                operation,
                type(exc).__name__,
            )
            failed.emit(_message_for(exc))
            return

        def on_finished(result: Any) -> None:
            try:
                payload = shape(result) if shape else {"output": str(result)}
                encoded = json.dumps(payload)
            except Exception:  # noqa: BLE001 - optional result detail
                logger.exception(
                    "Result shaping failed after successful operation=%s",
                    operation,
                )
                encoded = json.dumps(_fallback_result_payload(result))
            self._release_outputs(claimed_outputs)
            logger.info("Job finished operation=%s", operation)
            finished.emit(encoded)

        def on_failed(exc: Exception) -> None:
            self._release_outputs(claimed_outputs)
            logger.error(
                "Job failed operation=%s error=%s",
                operation,
                type(exc).__name__,
            )
            failed.emit(_message_for(exc))

        logger.info("Job started operation=%s", operation)
        self._jobs.start(fn, *args, on_finished=on_finished, on_failed=on_failed, **kwargs)

    @Slot(str, str)
    def runSplit(self, input_path: str, ranges_json: str) -> None:
        from pawdf.core.split import split_by_ranges

        out_dir = self._out_dir(input_path, "_split")
        self._dispatch(
            self.splitFinished,
            self.splitFailed,
            split_by_ranges,
            input_path,
            json.loads(ranges_json),
            out_dir,
            shape=lambda paths: {
                "outputs": [str(p) for p in paths],
                "count": len(paths),
                "where": str(out_dir),
            },
        )

    @Slot(str)
    def runMerge(self, paths_json: str) -> None:
        from pawdf.core.merge import merge_pdfs

        paths = json.loads(paths_json)
        out_path = self._out_file(paths[0] if paths else "merged", ".pdf", tag="_merged")
        self._dispatch(self.mergeFinished, self.mergeFailed, merge_pdfs, paths, out_path)

    @Slot(str, str)
    def runOrganize(self, input_path: str, edits_json: str) -> None:
        from pawdf.core.organize import apply_page_edits

        edits = [(int(index), int(rotation)) for index, rotation in json.loads(edits_json)]
        self._dispatch(
            self.organizeFinished,
            self.organizeFailed,
            apply_page_edits,
            input_path,
            edits,
            self._out_file(input_path, ".pdf", tag="_organized"),
        )

    @Slot(str, str, int)
    def runRasterize(self, input_path: str, fmt: str, dpi: int) -> None:
        from pawdf.core.rasterize import pdf_to_images

        out_dir = self._out_dir(input_path, "_pages")
        self._dispatch(
            self.rasterizeFinished,
            self.rasterizeFailed,
            pdf_to_images,
            input_path,
            out_dir,
            shape=lambda paths: {
                "outputs": [str(p) for p in paths],
                "count": len(paths),
                "where": str(out_dir),
            },
            dpi=dpi,
            fmt=fmt,
        )

    @Slot(str, str)
    def runImagePdf(self, paths_json: str, fit: str) -> None:
        from pawdf.core.imagepdf import images_to_pdf

        paths = json.loads(paths_json)
        self._dispatch(
            self.imagepdfFinished,
            self.imagepdfFailed,
            images_to_pdf,
            paths,
            self._out_file(paths[0] if paths else "images", ".pdf"),
            fit=fit,
        )

    @Slot(str)
    def runPdfToWord(self, input_path: str) -> None:
        from pawdf.core.pdf_to_docx import pdf_to_docx

        self._dispatch(
            self.pdfToWordFinished,
            self.pdfToWordFailed,
            pdf_to_docx,
            input_path,
            self._out_file(input_path, ".docx"),
        )

    @Slot(str)
    def runWordToPdf(self, input_path: str) -> None:
        from pawdf.core.docx_to_pdf import docx_to_pdf

        self._dispatch(
            self.wordToPdfFinished,
            self.wordToPdfFailed,
            docx_to_pdf,
            input_path,
            self._out_file(input_path, ".pdf"),
        )

    @Slot(str, str)
    def runCompress(self, input_path: str, preset: str) -> None:
        from pawdf.core.compress import compress_pdf

        self._dispatch(
            self.compressFinished,
            self.compressFailed,
            compress_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_compressed"),
            shape=lambda r: {
                "output": str(r.output_path),
                "method": r.method,
                "originalSize": r.original_size,
                "compressedSize": r.compressed_size,
                "ratio": r.ratio,
            },
            preset=preset,
        )

    @Slot(str, str, bool)
    def runRotate(self, input_path: str, degrees_and_pages: str, absolute: bool) -> None:
        from pawdf.core.rotate import rotate_pdf

        options = json.loads(degrees_and_pages)
        self._dispatch(
            self.rotateFinished,
            self.rotateFailed,
            rotate_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_rotated"),
            degrees=int(options["degrees"]),
            pages=options.get("pages") or None,
            absolute=absolute,
        )

    @Slot(str, str)
    def runCrop(self, input_path: str, options_json: str) -> None:
        from pawdf.core.crop import Margins, crop_pdf

        options = json.loads(options_json)
        margins = Margins(
            left=float(options.get("left", 0)),
            top=float(options.get("top", 0)),
            right=float(options.get("right", 0)),
            bottom=float(options.get("bottom", 0)),
        )
        self._dispatch(
            self.cropFinished,
            self.cropFailed,
            crop_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_cropped"),
            margins=margins,
            pages=options.get("pages") or None,
        )

    @Slot(str)
    def runRepair(self, input_path: str) -> None:
        from pawdf.core.repair import repair_pdf

        self._dispatch(
            self.repairFinished,
            self.repairFailed,
            repair_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_repaired"),
            shape=lambda r: {
                "output": str(r.output_path),
                "pages": r.pages_recovered,
                "wasAlreadyReadable": r.was_already_readable,
                "isNowClean": r.is_now_clean,
                "warnings": r.warnings[:4],
            },
        )

    @Slot(str, str)
    def runProtect(self, input_path: str, options_json: str) -> None:
        from pawdf.core.protect import Permissions, protect_pdf

        options = json.loads(options_json)
        self._dispatch(
            self.protectFinished,
            self.protectFailed,
            protect_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_protected"),
            password=options["password"],
            permissions=Permissions(
                print=bool(options.get("allowPrint", True)),
                modify=bool(options.get("allowModify", True)),
                extract=bool(options.get("allowExtract", True)),
                annotate=bool(options.get("allowAnnotate", True)),
            ),
        )

    @Slot(str, str)
    def runUnlock(self, input_path: str, password: str) -> None:
        from pawdf.core.protect import unlock_pdf

        self._dispatch(
            self.unlockFinished,
            self.unlockFailed,
            unlock_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_unlocked"),
            password=password,
        )

    @Slot(str, result=bool)
    def isEncrypted(self, path: str) -> bool:
        """Lets the Unlock panel say up front that a file needs no unlocking."""
        from pawdf.core.protect import is_encrypted

        try:
            return is_encrypted(path)
        except (PawdfError, OSError):
            return False

    @Slot(str, str)
    def runWatermark(self, input_path: str, options_json: str) -> None:
        from pawdf.core.stamp import add_watermark

        options = json.loads(options_json)
        self._dispatch(
            self.watermarkFinished,
            self.watermarkFailed,
            add_watermark,
            input_path,
            self._out_file(input_path, ".pdf", tag="_watermarked"),
            text=options["text"],
            position=options.get("position", "center"),
            opacity=float(options.get("opacity", 0.18)),
            rotation=float(options.get("rotation", 45)),
            font_size=float(options.get("fontSize", 52)),
            colour=options.get("colour", "#808080"),
            pages=options.get("pages") or None,
        )

    @Slot(str, str, str)
    def runSign(self, input_path: str, image_path: str, options_json: str) -> None:
        from pawdf.core.stamp import stamp_image

        options = json.loads(options_json)
        self._dispatch(
            self.signFinished,
            self.signFailed,
            stamp_image,
            input_path,
            self._out_file(input_path, ".pdf", tag="_signed"),
            image_path=image_path,
            position=options.get("position", "bottom-right"),
            width_pt=float(options.get("width", 140)),
            pages=options.get("pages") or None,
        )

    @Slot(str, str)
    def runPageNumbers(self, input_path: str, options_json: str) -> None:
        from pawdf.core.stamp import add_page_numbers

        options = json.loads(options_json)
        self._dispatch(
            self.pagenumbersFinished,
            self.pagenumbersFailed,
            add_page_numbers,
            input_path,
            self._out_file(input_path, ".pdf", tag="_numbered"),
            position=options.get("position", "bottom-center"),
            start_at=int(options.get("startAt", 1)),
            template=options.get("template", "{n}"),
            skip_first=bool(options.get("skipFirst", False)),
        )

    @Slot(str, bool)
    def runMarkdown(self, input_path: str, page_separators: bool) -> None:
        from pawdf.core.pdf_to_markdown import pdf_to_markdown

        self._dispatch(
            self.markdownFinished,
            self.markdownFailed,
            pdf_to_markdown,
            input_path,
            self._out_file(input_path, ".md"),
            page_separators=page_separators,
        )

    @Slot(str)
    def runXlsxToPdf(self, input_path: str) -> None:
        from pawdf.core.xlsx_to_pdf import xlsx_to_pdf

        self._dispatch(
            self.xlsxToPdfFinished,
            self.xlsxToPdfFailed,
            xlsx_to_pdf,
            input_path,
            self._out_file(input_path, ".pdf"),
        )

    @Slot(str)
    def runPptxToPdf(self, input_path: str) -> None:
        from pawdf.core.pptx_to_pdf import pptx_to_pdf_detailed

        self._dispatch(
            self.pptxToPdfFinished,
            self.pptxToPdfFailed,
            pptx_to_pdf_detailed,
            input_path,
            self._out_file(input_path, ".pdf"),
            shape=lambda result: {
                "output": str(result.output_path),
                "warnings": result.warnings[:50],
                "warningCount": len(result.warnings),
                "shapesRendered": result.shapes_rendered,
                "shapesSkipped": result.shapes_skipped,
            },
        )

    @Slot(str, str, int)
    def runOcr(self, input_path: str, language: str, dpi: int) -> None:
        from pawdf.core.ocr import ocr_pdf

        self._dispatch(
            self.ocrFinished,
            self.ocrFailed,
            ocr_pdf,
            input_path,
            self._out_file(input_path, ".pdf", tag="_searchable"),
            shape=lambda r: {
                "output": str(r.output_path),
                "pages": r.pages_processed,
                "failed": r.failed_pages,
            },
            language=language or "eng",
            dpi=dpi,
        )

    @Slot(str, result=str)
    def formFields(self, path: str) -> str:
        """The fields in a PDF, so the panel can build an input per field."""
        from dataclasses import asdict

        from pawdf.core.forms import list_fields

        try:
            return json.dumps([asdict(f) for f in list_fields(path)])
        except (PawdfError, OSError):
            return "[]"

    @Slot(str, str, bool)
    def runFillForm(self, input_path: str, values_json: str, flatten: bool) -> None:
        from pawdf.core.forms import fill_form

        self._dispatch(
            self.formsFinished,
            self.formsFailed,
            fill_form,
            input_path,
            self._out_file(input_path, ".pdf", tag="_filled"),
            {str(k): str(v) for k, v in json.loads(values_json).items()},
            flatten=flatten,
        )

    @Slot(str, str)
    def runAnnotate(self, input_path: str, options_json: str) -> None:
        from pawdf.core.annotate import add_note

        options = json.loads(options_json)
        self._dispatch(
            self.annotateFinished,
            self.annotateFailed,
            add_note,
            input_path,
            self._out_file(input_path, ".pdf", tag="_annotated"),
            text=options["text"],
            page=int(options.get("page", 1)) - 1,
            x=float(options.get("x", 72)),
            y=float(options.get("y", 720)),
            size=float(options.get("size", 12)),
            colour=options.get("colour", "#c9343b"),
        )

    # ------------------------------------------------------------ settings --

    @Slot(result=str)
    def tesseractStatus(self) -> str:
        """Whether OCR is available, and what to install if not."""
        from pawdf.core.ocr.tesseract import (
            available_languages,
            find_tesseract,
            install_instructions,
        )

        found = find_tesseract()
        return json.dumps(
            {
                "found": found is not None,
                "path": str(found) if found else "",
                "languages": available_languages(),
                "instructions": "" if found else install_instructions(),
            }
        )

    @Slot(result=str)
    def ghostscriptStatus(self) -> str:
        from pawdf.core.compress.ghostscript import find_ghostscript

        found = find_ghostscript()
        return json.dumps({"found": found is not None, "path": str(found) if found else ""})

    @Slot()
    def setupGhostscript(self) -> None:
        from pawdf.core.compress.ghostscript import run_setup

        self._dispatch(
            self.ghostscriptFinished,
            self.ghostscriptFailed,
            run_setup,
            shape=lambda result: (
                {"instructions": result} if isinstance(result, str) else {"path": str(result)}
            ),
        )

    # ---------------------------------------------------------- thumbnails --

    @Slot(str, result=int)
    def pageCount(self, path: str) -> int:
        from pawdf.core.rasterize import page_count

        try:
            return page_count(path)
        except (PawdfError, OSError):
            return 0

    @Slot(str, int)
    def requestThumbnail(self, path: str, page_index: int) -> None:
        """Render one page thumbnail, off the UI thread, answering with its
        index alongside the image.

        The reply carries both the document and the page index. The index
        matters because replies are not guaranteed to arrive in the order they
        were requested, and appending them as they land would mislabel pages.
        The path matters because more than one document can be on screen at
        once, and a reply with no sender can be filed against the wrong one.
        """

        def render() -> dict[str, Any]:
            from PIL import Image

            from pawdf.core.rasterize import render_page

            rendered = render_page(path, page_index, dpi=THUMBNAIL_DPI)
            image = Image.frombytes("RGBA", (rendered.width, rendered.height), rendered.rgba)
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
            return {
                "path": path,
                "index": page_index,
                "dataUrl": f"data:image/png;base64,{encoded}",
                "error": "",
            }

        def on_finished(payload: dict[str, Any]) -> None:
            self.thumbnailReady.emit(json.dumps(payload))

        def on_failed(exc: Exception) -> None:
            # Still answer, so the grid can count this page as settled and
            # finish loading instead of waiting forever for a reply that a
            # raised exception would never have sent.
            self.thumbnailReady.emit(
                json.dumps(
                    {
                        "path": path,
                        "index": page_index,
                        "dataUrl": "",
                        "error": _message_for(exc),
                    }
                )
            )

        self._jobs.start(render, on_finished=on_finished, on_failed=on_failed)

    # ------------------------------------------------- native drag-and-drop --

    def handle_dropped_files(self, paths: list[str]) -> None:
        """Called from the Qt side (see dnd.py), not from JavaScript."""
        self.filesDropped.emit(json.dumps(paths))

    def handle_drag_state(self, active: bool) -> None:
        self.dragStateChanged.emit(active)

    # -------------------------------------------------------------- teardown --

    def shutdown(self, msecs: int = -1) -> bool:
        """Wait for every in-flight write to finish before teardown."""
        return self._jobs.wait_all(msecs)
