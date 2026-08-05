"""A description of every feature package, in data rather than in the UI.

The UI builds its tool ring from this list: adding a feature means adding a
`Feature` here, not editing HTML. Nothing in this module imports a feature -
it holds names and metadata only, so reading the registry costs nothing and
stays honest about the fact that features don't depend on each other.

`import_path` is resolved lazily by whoever needs it (see `load`), which is
what keeps a heavy library out of startup until its tool is actually used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import ModuleType

__all__ = ["CATEGORIES", "FEATURES", "Category", "Feature", "by_id", "in_category", "load"]


@dataclass(frozen=True)
class Category:
    """A group of tools. The UI's first ring is these, not the tools.

    Eight tools fit in a circle. Twenty do not: they collide, or they shrink
    past the point of being readable. So the ring shows categories and expands
    one at a time, and anyone who already knows the tool's name skips the
    ring entirely with the search box.
    """

    id: str
    title: str
    tagline: str
    #: Hue in degrees, shared by every tool in the category so the expanded
    #: ring still reads as a group. Red is reserved for Add files.
    hue: int


# A category is declared when its first tool lands, never before: an empty
# category is a ring node that opens onto nothing, and a test enforces it.
CATEGORIES: tuple[Category, ...] = (
    Category("organise", "Organize", "Split, merge, reorder, rotate, crop", 200),
    Category("convert", "Convert", "To and from Word, images, Markdown", 250),
    Category("optimise", "Optimize", "Compress, repair, make text searchable", 160),
    Category("secure", "Secure", "Passwords, watermarks, signatures", 30),
    Category("annotate", "Annotate", "Page numbers and notes", 300),
)


@dataclass(frozen=True)
class Feature:
    """One user-facing operation, and everything the UI needs to present it."""

    id: str
    title: str
    tagline: str
    import_path: str
    #: pip requirements this feature needs on its own, for the README tables
    #: and for the per-feature extras in pyproject.toml.
    requires: tuple[str, ...]
    #: Which ring this tool lives in. Must match a Category id.
    category: str
    #: Input file extensions this tool can open.
    accepts: tuple[str, ...] = field(default=())
    #: Output file extensions. Nothing reads this yet; it is what the deferred
    #: workflow engine needs to reject an invalid chain before running it, and
    #: it costs nothing to record while each feature is fresh in mind.
    produces: tuple[str, ...] = field(default=(".pdf",))
    #: Per-tool hue override. Normally left alone: tools inherit their
    #: category's hue so an expanded ring reads as one group.
    hue: int | None = None


FEATURES: tuple[Feature, ...] = (
    Feature(
        id="split",
        title="Split",
        tagline="Break one PDF into several, by page range",
        import_path="pawdf.core.split",
        requires=("pikepdf",),
        category="organise",
        accepts=(".pdf",),
    ),
    Feature(
        id="merge",
        title="Merge",
        tagline="Combine PDFs into one, in any order",
        import_path="pawdf.core.merge",
        requires=("pikepdf",),
        category="organise",
        accepts=(".pdf",),
    ),
    Feature(
        id="organize",
        # "Arrange" in the UI, `organize` as the id. The id is load-bearing:
        # it names the package directory, the extras group in pyproject.toml,
        # and the PyInstaller hidden import, so it stays put while the label
        # is free to be whatever reads best.
        title="Arrange",
        tagline="Reorder, rotate, and delete pages",
        import_path="pawdf.core.organize",
        requires=("pikepdf",),
        category="organise",
        accepts=(".pdf",),
    ),
    Feature(
        id="compress",
        title="Compress",
        tagline="Make a PDF smaller, with or without Ghostscript",
        import_path="pawdf.core.compress",
        requires=("pikepdf", "Pillow", "platformdirs"),
        category="optimise",
        accepts=(".pdf",),
    ),
    Feature(
        id="ocr",
        title="OCR",
        tagline="Make a scanned PDF searchable",
        import_path="pawdf.core.ocr",
        requires=("pypdfium2", "Pillow", "pikepdf"),
        category="optimise",
        accepts=(".pdf",),
    ),
    Feature(
        id="rasterize",
        title="PDF to Images",
        tagline="Render every page as PNG, JPG, or WebP",
        import_path="pawdf.core.rasterize",
        requires=("pypdfium2", "Pillow", "pikepdf"),
        category="convert",
        accepts=(".pdf",),
        produces=(".png", ".jpg", ".webp"),
    ),
    Feature(
        id="imagepdf",
        title="Images to PDF",
        tagline="Combine images into one PDF, losslessly",
        import_path="pawdf.core.imagepdf",
        requires=("pikepdf", "Pillow"),
        category="convert",
        accepts=(".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"),
    ),
    Feature(
        id="rotate",
        title="Rotate",
        tagline="Turn every page, or a chosen range",
        import_path="pawdf.core.rotate",
        requires=("pikepdf",),
        category="organise",
        accepts=(".pdf",),
    ),
    Feature(
        id="crop",
        title="Crop",
        tagline="Trim margins or crop to a region",
        import_path="pawdf.core.crop",
        requires=("pikepdf",),
        category="organise",
        accepts=(".pdf",),
    ),
    Feature(
        id="repair",
        title="Repair",
        tagline="Recover a damaged or unreadable PDF",
        import_path="pawdf.core.repair",
        requires=("pikepdf",),
        category="optimise",
        accepts=(".pdf",),
    ),
    Feature(
        id="protect",
        title="Protect",
        tagline="Lock a PDF with a password",
        import_path="pawdf.core.protect",
        requires=("pikepdf",),
        category="secure",
        accepts=(".pdf",),
    ),
    Feature(
        id="unlock",
        # Same package as protect: one subject read forwards and backwards,
        # which is why the 1:1 rule between tools and directories is relaxed.
        title="Unlock",
        tagline="Remove a password you already know",
        import_path="pawdf.core.protect",
        requires=("pikepdf",),
        category="secure",
        accepts=(".pdf",),
    ),
    Feature(
        id="watermark",
        title="Watermark",
        tagline="Stamp text across every page",
        import_path="pawdf.core.stamp",
        requires=("pikepdf", "reportlab", "Pillow"),
        category="secure",
        accepts=(".pdf",),
    ),
    Feature(
        id="sign",
        title="Sign",
        # A visual mark, not a cryptographic signature. The panel says so:
        # promising more than that would be worse than offering less.
        tagline="Place a signature or stamp image on the page",
        import_path="pawdf.core.stamp",
        requires=("pikepdf", "reportlab", "Pillow"),
        category="secure",
        accepts=(".pdf",),
    ),
    Feature(
        id="pagenumbers",
        title="Page numbers",
        tagline="Number the pages, with a custom format",
        import_path="pawdf.core.stamp",
        requires=("pikepdf", "reportlab", "Pillow"),
        category="annotate",
        accepts=(".pdf",),
    ),
    Feature(
        id="pdf_to_docx",
        title="PDF to Word",
        tagline="Convert to an editable .docx",
        import_path="pawdf.core.pdf_to_docx",
        requires=("pypdfium2", "python-docx"),
        category="convert",
        accepts=(".pdf",),
        produces=(".docx",),
    ),
    Feature(
        id="forms",
        title="Fill form",
        tagline="Fill in an interactive PDF form",
        import_path="pawdf.core.forms",
        requires=("pikepdf",),
        category="annotate",
        accepts=(".pdf",),
    ),
    Feature(
        id="annotate",
        title="Annotate",
        tagline="Add notes and highlights on top of a page",
        import_path="pawdf.core.annotate",
        requires=("pikepdf", "reportlab"),
        category="annotate",
        accepts=(".pdf",),
    ),
    Feature(
        id="pdf_to_markdown",
        title="PDF to Markdown",
        tagline="Export clean Markdown for notes, wikis and LLMs",
        import_path="pawdf.core.pdf_to_markdown",
        requires=("pypdfium2", "pikepdf"),
        category="convert",
        accepts=(".pdf",),
        produces=(".md",),
    ),
    Feature(
        id="xlsx_to_pdf",
        title="Excel to PDF",
        tagline="Render a workbook, one section per sheet",
        import_path="pawdf.core.xlsx_to_pdf",
        requires=("openpyxl", "reportlab"),
        category="convert",
        accepts=(".xlsx",),
    ),
    Feature(
        id="pptx_to_pdf",
        title="PowerPoint to PDF",
        tagline="One slide per page, at the deck's own shape",
        import_path="pawdf.core.pptx_to_pdf",
        requires=("python-pptx", "reportlab", "Pillow"),
        category="convert",
        accepts=(".pptx",),
    ),
    Feature(
        id="docx_to_pdf",
        title="Word to PDF",
        tagline="Convert .docx without Word or LibreOffice",
        import_path="pawdf.core.docx_to_pdf",
        requires=("python-docx", "reportlab", "Pillow"),
        category="convert",
        accepts=(".docx",),
    ),
)


def category_of(feature: Feature) -> Category:
    """The category a feature belongs to."""
    for category in CATEGORIES:
        if category.id == feature.category:
            return category
    raise KeyError(f"Unknown category: {feature.category!r}")


def hue_of(feature: Feature) -> int:
    """The colour the UI paints this tool, its own or its category's."""
    return feature.hue if feature.hue is not None else category_of(feature).hue


def in_category(category_id: str) -> tuple[Feature, ...]:
    """Every feature in a category, in declaration order."""
    return tuple(f for f in FEATURES if f.category == category_id)


def by_id(feature_id: str) -> Feature:
    """Look up a feature, raising KeyError if the id is unknown."""
    for feature in FEATURES:
        if feature.id == feature_id:
            return feature
    raise KeyError(f"Unknown feature: {feature_id!r}")


def load(feature_id: str) -> ModuleType:
    """Import and return a feature's module.

    Deliberately lazy: importing `pawdf.core.registry` pulls in no PDF library
    at all, so the app can describe every tool it offers without paying for
    any of them until one is used.
    """
    return import_module(by_id(feature_id).import_path)
