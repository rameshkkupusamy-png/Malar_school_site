import math
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from portal.models import MAX_DOCUMENT_BYTES, Document
from portal.whatsapp import share_message


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


def test_page_groups_documents_in_fixed_order_newest_first(make_document, client):
    make_document("Trip form", Document.FORM)
    old = make_document("Old circular", Document.CIRCULAR)
    Document.objects.filter(pk=old.pk).update(added_at=timezone.now() - timedelta(days=5))
    make_document("New circular", Document.CIRCULAR)

    groups = client.get(reverse("portal:document_list")).context["groups"]

    assert [str(label) for label, _ in groups] == ["Circulars", "Forms"]
    assert [d.title for d in groups[0][1]] == ["New circular", "Old circular"]


def test_page_shows_note_type_and_size_but_not_hidden_documents(make_document, client):
    make_document("Trip form", Document.FORM, note="Return by Friday", content=b"x" * 2048)
    make_document("Draft", is_published=False)
    make_document("Expired", remove_after=timezone.localdate() - timedelta(days=1))

    html = client.get(reverse("portal:document_list")).content.decode()

    assert "Trip form" in html
    assert "Return by Friday" in html
    assert "PDF, 2.0\xa0KB" in html
    assert "Draft" not in html
    assert "Expired" not in html


@pytest.mark.django_db
def test_page_without_documents_says_so(client):
    html = client.get(reverse("portal:document_list")).content.decode()
    assert "No documents yet." in html


def test_page_survives_a_missing_file(make_document, client):
    document = make_document("Lost file")
    Path(document.file.path).unlink()

    response = client.get(reverse("portal:document_list"))

    assert response.status_code == 200
    assert "Lost file" in response.content.decode()


def test_permanent_link_opens_the_file_even_after_its_date(make_document, client):
    document = make_document(remove_after=timezone.localdate() - timedelta(days=30))

    response = client.get(document.get_absolute_url())

    assert response.status_code == 302
    assert response["Location"] == document.file.url


def test_permanent_link_works_for_tamil_file_names(make_document, client):
    document = make_document(name="சுற்றறிக்கை 1.pdf")

    response = client.get(document.get_absolute_url())

    assert response.status_code == 302
    assert Path(document.file.path).exists()
    assert response["Location"] == document.file.url


def test_permanent_link_is_gone_for_drafts_and_unknown_numbers(make_document, client):
    draft = make_document(is_published=False)
    assert client.get(draft.get_absolute_url()).status_code == 404
    assert client.get(reverse("portal:document_open", args=[99999])).status_code == 404


@pytest.mark.django_db
def test_menu_links_to_documents(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert f'href="{reverse("portal:document_list")}"' in html


def test_whatsapp_message_has_title_note_and_permanent_link(make_document, settings):
    settings.SITE_URL = "https://school.example"
    document = make_document("Zoo trip form", note="Return by Friday")

    text = share_message(document)

    assert text.startswith("*Zoo trip form*\nReturn by Friday\n")
    assert text.endswith(f"https://school.example/documents/{document.pk}/")


def test_admin_offers_sharing_only_for_listed_documents(make_document, admin_client):
    make_document("Booklist")
    expired = make_document("Old form", remove_after=timezone.localdate() - timedelta(days=1))

    html = admin_client.get(reverse("admin:portal_document_changelist")).content.decode()
    assert html.count("Share on WhatsApp") == 1

    url = reverse("admin:portal_document_change", args=[expired.pk])
    html = admin_client.get(url).content.decode()
    assert "Share on WhatsApp" not in html
    assert "Not shown to parents" in html


def test_admin_upload_refuses_wrong_file_type(admin_client):
    response = admin_client.post(
        reverse("admin:portal_document_add"),
        {
            "title_ta": "Form",
            "group": Document.FORM,
            "file": SimpleUploadedFile("page.html", b"<html>"),
            "is_published": "on",
        },
    )
    assert response.status_code == 200
    assert "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file." in response.content.decode()
    assert not Document.objects.exists()


@pytest.mark.django_db
def test_editors_can_manage_documents():
    call_command("setup_roles", stdout=None)
    codenames = set(
        Group.objects.get(name="Editors").permissions.values_list("codename", flat=True)
    )
    assert {"add_document", "change_document", "delete_document", "view_document"} <= codenames
