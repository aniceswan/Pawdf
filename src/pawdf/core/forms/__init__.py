"""Read, fill and safely flatten interactive PDF forms."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pawdf.core._shared import (
    ConversionError,
    PawdfError,
    ensure_exists,
    ensure_parent_dir,
    open_pdf,
)

__all__ = ["FormField", "NoFormError", "fill_form", "list_fields"]


class NoFormError(PawdfError):
    """Raised when a PDF has no interactive form to fill."""

    def __init__(self, path: str):
        super().__init__(f"'{path}' has no fillable form fields.")
        self.path = path


@dataclass
class FormField:
    name: str
    kind: str
    value: str = ""
    options: list[str] = field(default_factory=list)
    read_only: bool = False
    page: int = 0


_KINDS = {"/Tx": "text", "/Btn": "button", "/Ch": "choice", "/Sig": "signature"}
_READ_ONLY_BIT = 1
_RADIO_BIT = 1 << 15
_PUSHBUTTON_BIT = 1 << 16


def _parents(annot):  # noqa: ANN001, ANN202 - pikepdf object iterator
    node = annot
    seen: set[tuple[int, int] | int] = set()
    for _ in range(32):
        if node is None:
            return
        identity = getattr(node, "objgen", None)
        key = identity if identity and identity != (0, 0) else id(node)
        if key in seen:
            return
        seen.add(key)
        yield node
        node = node.get("/Parent")


def _inherited(annot, key: str):  # noqa: ANN001, ANN202
    for node in _parents(annot):
        if key in node:
            return node[key]
    return None


def _field_name(annot) -> str:  # noqa: ANN001
    parts: list[str] = []
    for node in _parents(annot):
        if "/T" in node:
            part = str(node["/T"])
            if part and (not parts or parts[-1] != part):
                parts.append(part)
    return ".".join(reversed(parts))


def _value_holder(annot):  # noqa: ANN001, ANN202
    """The field dictionary that owns /V for this widget."""
    for node in _parents(annot):
        if "/T" in node:
            return node
    return annot


def _states_of(annot) -> list[str]:  # noqa: ANN001
    import pikepdf

    appearance = annot.get("/AP")
    if appearance is None or "/N" not in appearance:
        return []

    normal = appearance["/N"]
    if isinstance(normal, pikepdf.Stream) or not isinstance(normal, pikepdf.Dictionary):
        return []

    try:
        return [str(key) for key in normal.keys()]
    except (AttributeError, TypeError):
        return []


def _choice_options(annot) -> list[str]:  # noqa: ANN001
    import pikepdf

    raw = _inherited(annot, "/Opt")
    if raw is None:
        return []

    options: list[str] = []
    for item in raw:
        value = item[0] if isinstance(item, pikepdf.Array) and len(item) >= 2 else item
        text = str(value)
        if text not in options:
            options.append(text)
    return options


def _kind_of(annot) -> tuple[str, int]:  # noqa: ANN001
    raw_type = _inherited(annot, "/FT")
    kind = _KINDS.get(str(raw_type) if raw_type else "", "unknown")
    flags = int(_inherited(annot, "/Ff") or 0)
    if kind == "button":
        if flags & _PUSHBUTTON_BIT:
            kind = "pushbutton"
        elif flags & _RADIO_BIT:
            kind = "radio"
        else:
            kind = "checkbox"
    return kind, flags


def _extend_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def list_fields(input_path: str | Path) -> list[FormField]:
    """Return one UI field per fully qualified field name.

    Radio widgets are aggregated into one field with every export state,
    rather than exposing one duplicate input per widget.
    """
    p = ensure_exists(input_path)
    fields: dict[str, FormField] = {}

    with open_pdf(p) as pdf:
        if "/AcroForm" not in pdf.Root:
            return []

        for page_index, page in enumerate(pdf.pages):
            for annot in page.get("/Annots", []):
                if annot.get("/Subtype") != "/Widget":
                    continue

                name = _field_name(annot)
                if not name:
                    continue

                kind, flags = _kind_of(annot)
                holder = _value_holder(annot)
                value = holder.get("/V")
                options = (
                    _states_of(annot)
                    if kind in {"checkbox", "radio"}
                    else _choice_options(annot)
                    if kind == "choice"
                    else []
                )
                read_only = bool(flags & _READ_ONLY_BIT) or kind in {
                    "pushbutton",
                    "signature",
                    "unknown",
                }

                existing = fields.get(name)
                if existing is None:
                    existing = FormField(
                        name=name,
                        kind=kind,
                        value=str(value) if value is not None else "",
                        options=[],
                        read_only=read_only,
                        page=page_index,
                    )
                    fields[name] = existing
                else:
                    existing.read_only = existing.read_only or read_only
                    if value is not None:
                        existing.value = str(value)

                _extend_unique(existing.options, options)

    return list(fields.values())


def _truthy(value: str) -> bool:
    return value.strip().lower() not in {"", "0", "false", "off", "/off", "no", "none"}


def _normalise_state(value: str) -> str:
    value = value.strip()
    if not value:
        return "/Off"
    return value if value.startswith("/") else f"/{value}"


def _widgets_by_name(pdf) -> dict[str, list]:  # noqa: ANN001
    grouped: dict[str, list] = {}
    for page in pdf.pages:
        for annot in page.get("/Annots", []):
            if annot.get("/Subtype") != "/Widget":
                continue
            name = _field_name(annot)
            if name:
                grouped.setdefault(name, []).append(annot)
    return grouped


def _fill_button(widgets: list, value: str, *, radio: bool) -> None:
    import pikepdf

    available: list[str] = []
    for widget in widgets:
        _extend_unique(available, [state for state in _states_of(widget) if state != "/Off"])

    requested = _normalise_state(value)
    if requested != "/Off" and requested not in available:
        if radio:
            expected = [option.removeprefix("/") for option in available]
            raise ValueError(f"Unknown radio option '{value}'. Expected one of {expected}.")
        requested = available[0] if available and _truthy(value) else "/Off"

    if not radio and requested == "/Off" and _truthy(value) and available:
        requested = available[0]

    holder = _value_holder(widgets[0])
    holder["/V"] = pikepdf.Name(requested)

    for widget in widgets:
        states = _states_of(widget)
        widget_state = requested if requested in states else "/Off"
        widget["/AS"] = pikepdf.Name(widget_state)


def _fill_text_or_choice(widgets: list, value: str, *, choice: bool) -> None:
    import pikepdf

    holder = _value_holder(widgets[0])
    holder["/V"] = pikepdf.String(value)
    if choice and "/I" in holder:
        del holder["/I"]

    for widget in widgets:
        if "/AP" in widget:
            del widget["/AP"]


def _flatten_form_widgets(pdf) -> None:  # noqa: ANN001
    """Flatten form widgets while preserving unrelated annotations."""
    import pikepdf

    preserved: list[list] = []
    for page in pdf.pages:
        annots = list(page.get("/Annots", []))
        widgets = [annot for annot in annots if annot.get("/Subtype") == "/Widget"]
        others = [annot for annot in annots if annot.get("/Subtype") != "/Widget"]
        preserved.append(others)
        if widgets:
            page["/Annots"] = pikepdf.Array(widgets)
        elif "/Annots" in page:
            del page["/Annots"]

    try:
        pdf.flatten_annotations()
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise ConversionError(
            "Could not flatten the form safely; the output was not written. "
            f"Appearance flattening failed: {exc}"
        ) from exc

    for page, others in zip(pdf.pages, preserved, strict=True):
        if others:
            page["/Annots"] = pikepdf.Array(others)
        elif "/Annots" in page:
            del page["/Annots"]

    if "/AcroForm" in pdf.Root:
        del pdf.Root["/AcroForm"]


def fill_form(
    input_path: str | Path,
    out_path: str | Path,
    values: dict[str, str],
    *,
    flatten: bool = False,
) -> Path:
    """Fill supported fields and optionally bake their generated appearances."""
    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    with open_pdf(p) as pdf:
        if "/AcroForm" not in pdf.Root:
            raise NoFormError(str(p))

        grouped = _widgets_by_name(pdf)
        for name, raw_value in values.items():
            widgets = grouped.get(name)
            if not widgets:
                continue

            kind, flags = _kind_of(widgets[0])
            if flags & _READ_ONLY_BIT:
                continue

            value = str(raw_value)
            if kind == "checkbox":
                _fill_button(widgets, value, radio=False)
            elif kind == "radio":
                _fill_button(widgets, value, radio=True)
            elif kind == "text":
                _fill_text_or_choice(widgets, value, choice=False)
            elif kind == "choice":
                _fill_text_or_choice(widgets, value, choice=True)
            # Signatures, push buttons and unknown field types remain untouched.

        pdf.Root.AcroForm["/NeedAppearances"] = True

        if flatten:
            try:
                pdf.generate_appearance_streams()
            except Exception as exc:  # noqa: BLE001 - fail closed, never erase values
                raise ConversionError(
                    f"Could not generate the visual form values, so flattening was cancelled: {exc}"
                ) from exc
            _flatten_form_widgets(pdf)

        pdf.save(out_path)

    return out_path
