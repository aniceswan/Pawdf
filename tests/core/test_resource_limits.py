from __future__ import annotations

import zipfile

import pytest

from pawdf.core._shared import ConversionError, ResourceLimitError
from pawdf.core._shared.limits import preflight_inputs, validate_input_file


def test_empty_input_is_rejected(tmp_path):
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(ResourceLimitError, match="empty"):
        validate_input_file(empty)


def test_per_file_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWDF_MAX_INPUT_MIB", "1")
    large = tmp_path / "large.bin"
    with large.open("wb") as stream:
        stream.truncate(2 * 1024 * 1024)
    with pytest.raises(ResourceLimitError, match="per-file"):
        validate_input_file(large)


def test_total_selection_limit_understands_json_path_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWDF_MAX_TOTAL_INPUT_MIB", "1")
    paths = []
    for index in range(2):
        path = tmp_path / f"{index}.bin"
        path.write_bytes(b"x" * 600_000)
        paths.append(str(path))

    import json

    with pytest.raises(ResourceLimitError, match="selected files total"):
        preflight_inputs(json.dumps(paths))


def test_archive_path_traversal_is_rejected(tmp_path):
    office = tmp_path / "unsafe.docx"
    with zipfile.ZipFile(office, "w") as archive:
        archive.writestr("../outside.xml", "<x/>")
    with pytest.raises(ResourceLimitError, match="unsafe archive path"):
        validate_input_file(office)


def test_archive_member_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWDF_MAX_ARCHIVE_MEMBERS", "1")
    office = tmp_path / "many.docx"
    with zipfile.ZipFile(office, "w") as archive:
        archive.writestr("one.xml", "<x/>")
        archive.writestr("two.xml", "<x/>")
    with pytest.raises(ResourceLimitError, match="archive entries"):
        validate_input_file(office)


def test_archive_ratio_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWDF_MAX_ARCHIVE_RATIO", "2")
    office = tmp_path / "ratio.docx"
    with zipfile.ZipFile(office, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * 100_000)
    with pytest.raises(ResourceLimitError, match="compression ratio"):
        validate_input_file(office)


def test_pdf_page_limit_is_enforced(tmp_path, monkeypatch):
    import pikepdf

    monkeypatch.setenv("PAWDF_MAX_PDF_PAGES", "2")
    source = tmp_path / "pages.pdf"
    with pikepdf.new() as pdf:
        for _ in range(3):
            pdf.add_blank_page()
        pdf.save(source)

    with pytest.raises(ResourceLimitError, match="3 pages"):
        validate_input_file(source)


def test_image_pixel_limit_is_enforced(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.setenv("PAWDF_MAX_IMAGE_MEGAPIXELS", "1")
    source = tmp_path / "large.png"
    Image.new("RGB", (1100, 1100)).save(source)

    with pytest.raises(ResourceLimitError, match="megapixels"):
        validate_input_file(source)


def test_unreadable_office_container_keeps_conversion_error_contract(tmp_path):
    broken = tmp_path / "broken.pptx"
    broken.write_bytes(b"not an Office archive")
    with pytest.raises(ConversionError, match="readable Office"):
        validate_input_file(broken)


def test_preflight_ignores_nonexistent_path_outputs(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"input")
    output = tmp_path / "not-created-yet" / "result.pdf"

    assert preflight_inputs(source, output) == [source]
