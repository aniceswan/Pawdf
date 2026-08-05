import pytest

from pawdf.core.forms import NoFormError, fill_form, list_fields


@pytest.fixture
def form_pdf(tmp_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = tmp_path / "form.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 740, "Application")
    form = c.acroForm
    form.textfield(name="fullname", x=72, y=690, width=200, height=20, value="")
    form.textfield(name="email", x=72, y=660, width=200, height=20, value="")
    form.checkbox(name="agree", x=72, y=630, checked=False)
    form.radio(name="plan", value="basic", x=72, y=600, selected=True)
    form.radio(name="plan", value="pro", x=112, y=600, selected=False)
    c.showPage()
    c.save()
    return path


def test_lists_every_field_with_its_kind(form_pdf):
    kinds = {f.name: f.kind for f in list_fields(form_pdf)}

    assert kinds["fullname"] == "text"
    assert kinds["agree"] == "checkbox"
    assert kinds["plan"] == "radio"


def test_text_fields_report_no_states(form_pdf):
    """A text field's /AP /N is a stream, and reading its keys returns stream
    plumbing that would look like a list of options.
    """
    text_field = next(f for f in list_fields(form_pdf) if f.name == "fullname")

    assert text_field.options == []


def test_buttons_report_the_states_the_document_names(form_pdf):
    """A checkbox's "on" state is chosen by the document, not by the spec."""
    checkbox = next(f for f in list_fields(form_pdf) if f.name == "agree")

    assert "/Off" in checkbox.options
    assert any(state != "/Off" for state in checkbox.options)


def test_filling_text_fields(form_pdf, tmp_path):
    out = fill_form(form_pdf, tmp_path / "out.pdf", {"fullname": "Ada", "email": "a@b.c"})

    values = {f.name: f.value for f in list_fields(out)}
    assert values["fullname"] == "Ada"
    assert values["email"] == "a@b.c"


def test_filling_a_checkbox_uses_the_documents_on_state(form_pdf, tmp_path):
    out = fill_form(form_pdf, tmp_path / "out.pdf", {"agree": "yes"})

    checkbox = next(f for f in list_fields(out) if f.name == "agree")
    assert checkbox.value != "/Off"


def test_a_checkbox_can_be_cleared(form_pdf, tmp_path):
    ticked = fill_form(form_pdf, tmp_path / "on.pdf", {"agree": "yes"})
    cleared = fill_form(ticked, tmp_path / "off.pdf", {"agree": ""})

    checkbox = next(f for f in list_fields(cleared) if f.name == "agree")
    assert checkbox.value == "/Off"


def test_stale_appearances_are_dropped(form_pdf, tmp_path):
    """A field carries a drawn picture of its old value; leaving it means the
    reader shows the form unchanged.
    """
    import pikepdf

    out = fill_form(form_pdf, tmp_path / "out.pdf", {"fullname": "Ada"})

    with pikepdf.open(out) as pdf:
        assert pdf.Root.AcroForm.get("/NeedAppearances")


def test_unknown_field_names_are_ignored(form_pdf, tmp_path):
    """A form whose fields were renamed should still take the ones that match."""
    out = fill_form(form_pdf, tmp_path / "out.pdf", {"nope": "x", "fullname": "Ada"})

    values = {f.name: f.value for f in list_fields(out)}
    assert values["fullname"] == "Ada"


def test_flattening_removes_the_form(form_pdf, tmp_path):
    out = fill_form(form_pdf, tmp_path / "flat.pdf", {"fullname": "Grace"}, flatten=True)

    assert list_fields(out) == []


def test_a_pdf_without_a_form(sample_pdf, tmp_path):
    assert list_fields(sample_pdf) == []

    with pytest.raises(NoFormError):
        fill_form(sample_pdf, tmp_path / "out.pdf", {"a": "b"})
