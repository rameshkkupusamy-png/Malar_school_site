import math
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from portal.models import MAX_DOCUMENT_BYTES, Document


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def make_document(db):
    def _make(
        title="Booklist", group=Document.LIST, name="file.pdf", content=b"%PDF-1.4", **fields
    ):
        return Document.objects.create(
            title=title, group=group, file=SimpleUploadedFile(name, content), **fields
        )

    return _make


def unsaved(name, content=b"x", title="Booklist"):
    return Document(title=title, group=Document.LIST, file=SimpleUploadedFile(name, content))


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["page.html", "logo.svg", "run.exe", "notes.txt"])
def test_only_office_files_pdfs_and_photos_are_accepted(name):
    with pytest.raises(ValidationError) as error:
        unsaved(name).full_clean()
    assert error.value.message_dict["file"] == [
        "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["form.pdf", "FORM.PDF", "list.xlsx", "photo.JPG"])
def test_allowed_files_pass(name):
    unsaved(name).full_clean()


@pytest.mark.django_db
def test_files_over_10_mb_are_refused_with_their_size():
    document = unsaved("big.pdf", b"0" * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(ValidationError) as error:
        document.full_clean()
    size = math.ceil((MAX_DOCUMENT_BYTES + 1) / 1024 / 1024)
    assert error.value.message_dict["file"] == [
        f"This file is {size} MB. The limit is 10 MB. Try saving the PDF at a smaller size."
    ]


@pytest.mark.django_db
def test_title_is_needed_in_one_language():
    with pytest.raises(ValidationError) as error:
        unsaved("form.pdf", title="").full_clean()
    assert "title_ta" in error.value.message_dict


def test_published_hides_drafts_and_documents_past_their_date(make_document):
    today = timezone.localdate()
    make_document("Draft", is_published=False)
    make_document("Expired", remove_after=today - timedelta(days=1))
    make_document("Last day", remove_after=today)
    make_document("Kept")

    titles = {d.title for d in Document.objects.published()}

    assert titles == {"Last day", "Kept"}


def test_file_type_and_size(make_document):
    document = make_document(name="form.pdf", content=b"x" * 2048)
    assert document.file_type == "PDF"
    assert document.file_size == "2.0\xa0KB"
    assert make_document(name="list.XLSX").file_type == "Excel"


def test_replacing_the_file_deletes_the_old_one(make_document):
    document = make_document(name="old.pdf")
    old_path = Path(document.file.path)

    document.file = SimpleUploadedFile("new.pdf", b"%PDF new")
    document.save()

    assert not old_path.exists()
    assert Path(document.file.path).exists()


def test_saving_without_a_new_file_keeps_it(make_document):
    document = make_document()
    path = Path(document.file.path)

    document.refresh_from_db()
    document.title = "Booklist 2027"
    document.save()

    assert path.exists()


def test_deleting_a_document_deletes_its_file(make_document):
    document = make_document()
    path = Path(document.file.path)

    document.delete()

    assert not path.exists()
