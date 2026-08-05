"""Tests for password protection.

These carry more weight than most: a "protected" file that anything can open
is worse than no protection, because it is believed. So the checks go through
pikepdf directly rather than trusting this package's own report.
"""

import pytest

from pawdf.core._shared import EncryptedPdfError, InvalidPdfError, page_count
from pawdf.core.protect import (
    Permissions,
    WrongPasswordError,
    is_encrypted,
    protect_pdf,
    unlock_pdf,
)


def test_protected_file_refuses_to_open_without_the_password(sample_pdf, tmp_path):
    import pikepdf

    locked = protect_pdf(sample_pdf, tmp_path / "locked.pdf", password="s3cret")

    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(locked)


def test_protected_file_opens_with_the_password(sample_pdf, tmp_path):
    import pikepdf

    locked = protect_pdf(sample_pdf, tmp_path / "locked.pdf", password="s3cret")

    with pikepdf.open(locked, password="s3cret") as pdf:
        assert len(pdf.pages) == page_count(sample_pdf)


def test_round_trip_preserves_the_document(sample_pdf, tmp_path):
    locked = protect_pdf(sample_pdf, tmp_path / "locked.pdf", password="pw")
    opened = unlock_pdf(locked, tmp_path / "open.pdf", password="pw")

    assert not is_encrypted(opened)
    assert page_count(opened) == page_count(sample_pdf)


def test_wrong_password_is_reported_as_such(sample_pdf, tmp_path):
    """Distinct from "this file is broken", because the fix is different."""
    locked = protect_pdf(sample_pdf, tmp_path / "locked.pdf", password="right")

    with pytest.raises(WrongPasswordError):
        unlock_pdf(locked, tmp_path / "out.pdf", password="wrong")


def test_is_encrypted(sample_pdf, encrypted_pdf, tmp_path):
    assert is_encrypted(sample_pdf) is False
    assert is_encrypted(encrypted_pdf) is True


def test_is_encrypted_rejects_a_corrupt_file(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    with pytest.raises(InvalidPdfError):
        is_encrypted(bad)


def test_permissions_are_recorded(sample_pdf, tmp_path):
    """Advisory, not enforced by cryptography, but they should at least say
    what was asked for.
    """
    import pikepdf

    out = protect_pdf(
        sample_pdf,
        tmp_path / "restricted.pdf",
        password="pw",
        permissions=Permissions(print=False, extract=False),
    )

    with pikepdf.open(out, password="pw") as pdf:
        assert pdf.allow.print_highres is False
        assert pdf.allow.extract is False
        # Accessibility is always allowed: withholding it only obstructs
        # screen readers, and every compliant reader ignores the flag anyway.
        assert pdf.allow.accessibility is True


def test_defaults_allow_everything(sample_pdf, tmp_path):
    import pikepdf

    out = protect_pdf(sample_pdf, tmp_path / "plain.pdf", password="pw")

    with pikepdf.open(out, password="pw") as pdf:
        assert pdf.allow.print_highres is True
        assert pdf.allow.extract is True


def test_empty_password_is_rejected(sample_pdf, tmp_path):
    with pytest.raises(ValueError):
        protect_pdf(sample_pdf, tmp_path / "out.pdf", password="")


def test_protecting_an_already_locked_file_says_so(encrypted_pdf, tmp_path):
    with pytest.raises(EncryptedPdfError):
        protect_pdf(encrypted_pdf, tmp_path / "out.pdf", password="new")


def test_unlocking_the_shared_encrypted_fixture(encrypted_pdf, tmp_path):
    opened = unlock_pdf(encrypted_pdf, tmp_path / "open.pdf", password="secret")
    assert not is_encrypted(opened)
