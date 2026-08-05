# `protect` - passwords on and off

```python
from pawdf.core.protect import protect_pdf, unlock_pdf, is_encrypted, Permissions

protect_pdf("in.pdf", "out.pdf", password="s3cret")
protect_pdf(
    "in.pdf", "out.pdf", password="s3cret", permissions=Permissions(print=False, extract=False)
)

unlock_pdf("locked.pdf", "open.pdf", password="s3cret")
is_encrypted("maybe.pdf")  # -> bool
```

Encryption is AES-256 (revision 6), the strongest scheme the PDF spec defines.

## What a PDF password actually protects

Worth being precise, because the two halves are not equally real:

- The **user password** is genuine protection. Without it the file's contents
  cannot be decrypted, by this or any other tool.
- The **owner password and permission flags** are a request. They say "please
  don't print this", and every compliant reader obeys while every
  non-compliant one ignores them. Treat them as a preference, not a control.

`owner_password` defaults to the user password. Leaving it empty would let
anyone strip the permissions without knowing anything at all.

`unlock_pdf` is not password cracking: you have to supply the password. It
exists so a file you already have access to stops asking every time.

## Lifting this out

| | |
|---|---|
| Depends on | `pawdf.core._shared` |
| pip packages | `pikepdf>=9.0` |
| Licenses pulled in | pikepdf: MPL-2.0 (bundles QPDF, Apache-2.0) |

Copy this directory and `core/_shared/`. Nothing else in this repo is needed.

## Errors

`WrongPasswordError` when unlock is given the wrong password,
`EncryptedPdfError` when protect is handed a file that is already locked,
`InvalidPdfError` for unreadable input, `ValueError` for an empty password.
