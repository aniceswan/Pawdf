"""Add or remove a PDF's password protection.

Both directions live in one package because they are the same subject read
forwards and backwards, and because splitting them would mean two copies of
the same permission handling.

A word on what PDF encryption actually buys you: the *user* password is real
protection, since the file's contents cannot be decrypted without it. The
*owner* password and the permission flags are not - they say "please don't
print this" and every compliant reader obeys, while every non-compliant one
ignores them. `protect_pdf` therefore treats the user password as the point
and the permissions as a courtesy.

Standalone feature package. See README.md in this directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pawdf.core._shared import (
    EncryptedPdfError,
    InvalidPdfError,
    PawdfError,
    ensure_exists,
    ensure_parent_dir,
)

__all__ = [
    "Permissions",
    "WrongPasswordError",
    "is_encrypted",
    "protect_pdf",
    "unlock_pdf",
]


class WrongPasswordError(PawdfError):
    """Raised when the password given to `unlock_pdf` doesn't open the file."""

    def __init__(self, path: str):
        super().__init__(f"That password doesn't open '{path}'.")
        self.path = path


@dataclass(frozen=True)
class Permissions:
    """What a reader may do with the file once it is open.

    Enforced only by cooperating readers, never cryptographically. Defaults
    allow everything, so protecting a file without thinking about permissions
    just means "needs a password to open".
    """

    print: bool = True
    modify: bool = True
    extract: bool = True
    annotate: bool = True


def is_encrypted(path: str | Path) -> bool:
    """True if `path` needs a password to open."""
    import pikepdf

    p = ensure_exists(path)
    try:
        with pikepdf.open(p):
            return False
    except pikepdf.PasswordError:
        return True
    except pikepdf.PdfError as exc:
        raise InvalidPdfError(str(p), detail=str(exc)) from exc


def protect_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    password: str,
    owner_password: str | None = None,
    permissions: Permissions | None = None,
) -> Path:
    """Write an encrypted copy of `input_path` that needs `password` to open.

    Uses AES-256 (revision 6), which is the strongest scheme the PDF spec
    defines. `owner_password` defaults to `password`: leaving it empty would
    let anyone strip the permissions without knowing anything.
    """
    import pikepdf

    if not password:
        raise ValueError("password must not be empty")

    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)
    allowed = permissions or Permissions()

    try:
        with pikepdf.open(p) as pdf:
            pdf.save(
                out_path,
                encryption=pikepdf.Encryption(
                    user=password,
                    owner=owner_password or password,
                    R=6,
                    allow=pikepdf.Permissions(
                        accessibility=True,
                        extract=allowed.extract,
                        modify_annotation=allowed.annotate,
                        modify_assembly=allowed.modify,
                        modify_form=allowed.modify,
                        modify_other=allowed.modify,
                        print_lowres=allowed.print,
                        print_highres=allowed.print,
                    ),
                ),
            )
    except pikepdf.PasswordError as exc:
        # Already protected, and we weren't given the password to open it.
        raise EncryptedPdfError(str(p)) from exc
    except pikepdf.PdfError as exc:
        raise InvalidPdfError(str(p), detail=str(exc)) from exc

    return out_path


def unlock_pdf(
    input_path: str | Path,
    out_path: str | Path,
    *,
    password: str = "",
) -> Path:
    """Write a copy of `input_path` with its encryption removed.

    This is not password *cracking*: the password has to be supplied. It
    removes the need to type it every time a file you already have access to
    is opened.
    """
    import pikepdf

    p = ensure_exists(input_path)
    out_path = ensure_parent_dir(out_path)

    try:
        with pikepdf.open(p, password=password) as pdf:
            # Saving without an `encryption=` argument writes it out in the
            # clear; pikepdf does not carry the original encryption over.
            pdf.save(out_path)
    except pikepdf.PasswordError as exc:
        raise WrongPasswordError(str(p)) from exc
    except pikepdf.PdfError as exc:
        raise InvalidPdfError(str(p), detail=str(exc)) from exc

    return out_path
