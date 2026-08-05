# `forms` - read and fill PDF form fields

```python
from pawdf.core.forms import list_fields, fill_form

for field in list_fields("application.pdf"):
    print(field.name, field.kind, field.value, field.options)

fill_form("application.pdf", "filled.pdf", {"fullname": "Ada Lovelace", "agree": "yes"})
fill_form("application.pdf", "final.pdf", {...}, flatten=True)
```

`list_fields` returns `FormField(name, kind, value, options, read_only, page)`.
`kind` is `text`, `checkbox`, `radio`, `choice`, `signature` or `unknown`.

## Filling, not authoring

Filling an existing form closes a real gap: without it the alternative is
printing, writing and scanning back. **Authoring** forms - creating widgets,
appearance streams, tab order, validation - is a much larger job and is not
attempted.

## Three details that are easy to get wrong

- **Fields inherit.** A widget usually gets its name, type and flags from a
  parent that defines the field, so every lookup walks up the tree.
- **A checkbox's "on" state is named by the document**, not by the spec. It
  might be `/Yes`, `/On` or `/1`. `options` reports what this particular field
  accepts, and `fill_form` maps a truthy value onto whichever it is.
- **Cached appearances lie.** A field carries a drawn picture of its old
  value; leaving it means a reader shows the form unchanged. It is dropped on
  fill and `/NeedAppearances` is set so readers redraw.

Only buttons have appearance *states*. For a text field, `/AP /N` is a stream,
and reading its keys returns stream plumbing (`/Filter`, `/BBox`) that would
look like a list of options.

## Flattening

A filled form is still a form: the values live in field objects and any reader
can change them again. `flatten=True` removes the interactive fields, leaving
what they drew. Use it before sending a completed form to someone else. It is
a one-way door.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`NoFormError` when a PDF has no interactive form. `list_fields` returns an
empty list instead, because asking "does this have a form?" is a normal thing
to do. Unknown field names passed to `fill_form` are ignored, so a form whose
fields were renamed still accepts the ones that match.
