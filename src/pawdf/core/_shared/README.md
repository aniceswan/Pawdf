# `core/_shared/` - the common base

This is the **only** module a feature package may import from another part of
`core/`. It exists so features do not grow dependencies on each other.

| File | What it holds | Third-party imports |
|---|---|---|
| `errors.py` | The `PawdfError` exception hierarchy | none |
| `paths.py` | validated input paths and output parents | none |
| `ranges.py` | `parse_page_ranges` for the `"1-3,5"` syntax | none |
| `pdf_io.py` | `open_pdf` / `page_count`, normalizing pikepdf errors | `pikepdf` lazily |
| `limits.py` | size, page, image-pixel and Office ZIP safety limits | pikepdf/Pillow lazily |

The larger shared base is deliberate: every lifted feature must keep the same
untrusted-input protections as the desktop application. Heavy libraries are
still imported only inside format-specific validation functions.

## Lifting a feature out of this repo

Copy the feature's directory plus this `_shared/` directory, then rewrite the
`pawdf.core._shared` imports to wherever you put it. Nothing else in this
repository is required: no Qt, registry, or app packaging. Each feature's own
README lists the pip packages it needs.

Environment overrides for the safety limits are documented in
`docs/production_readiness.md`.
