import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from portal.models import CommitteeMember, Document, Pibg


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def document(title, group=Document.PIBG, **fields):
    return Document.objects.create(
        title=title, group=group, file=SimpleUploadedFile("file.pdf", b"%PDF-1.4"), **fields
    )


@pytest.mark.django_db
def test_there_is_only_ever_one_record():
    assert Pibg.load().pk is None
    Pibg(term="2025/2026").save()
    Pibg(term="2026/2027").save()
    assert Pibg.objects.count() == 1
    assert Pibg.load().term == "2026/2027"


@pytest.mark.django_db
def test_unsaved_record_has_no_committee():
    assert Pibg.load().members() == []


@pytest.mark.django_db
def test_committee_follows_role_order_then_order_then_name():
    pibg = Pibg.objects.create(term="2026/2027")
    for name, role, order in [
        ("Cikgu Anand", CommitteeMember.MEMBER, 1),
        ("Puan Devi", CommitteeMember.MEMBER, 0),
        ("Puan Kavitha", CommitteeMember.TREASURER, 0),
        ("Encik Ravi", CommitteeMember.MEMBER, 0),
        ("Encik Arun", CommitteeMember.CHAIR, 0),
    ]:
        pibg.committee.create(name=name, role=role, order=order)

    assert [m.name for m in pibg.members()] == [
        "Encik Arun",
        "Puan Kavitha",
        "Encik Ravi",
        "Puan Devi",
        "Cikgu Anand",
    ]


def test_roles_are_in_display_order():
    assert [key for key, _label in CommitteeMember.ROLES] == [
        "chair",
        "vice_chair",
        "secretary",
        "assistant_secretary",
        "treasurer",
        "assistant_treasurer",
        "auditor",
        "advisor",
        "member",
    ]


def test_contact_links_only_for_what_is_filled_in():
    pibg = Pibg(phone="03-8723 1234", email="pibg@school.example")
    assert pibg.phone_link == "tel:+60387231234"
    assert pibg.email_link == "mailto:pibg@school.example"
    assert pibg.has_contact
    assert not Pibg().has_contact
    assert Pibg(whatsapp_group="https://chat.whatsapp.com/abc").has_contact


def test_stored_number_that_no_longer_checks_out_gives_no_link():
    pibg = Pibg(phone="12345")
    assert pibg.phone_link == ""
    assert not pibg.has_contact


def test_bad_phone_and_plain_http_group_link_are_refused():
    with pytest.raises(ValidationError) as error:
        Pibg(phone="12345").full_clean()
    assert "phone" in error.value.message_dict
    with pytest.raises(ValidationError) as error:
        Pibg(whatsapp_group="http://chat.whatsapp.com/abc").full_clean()
    assert "whatsapp_group" in error.value.message_dict


@pytest.mark.django_db
def test_documents_page_has_a_pibg_heading(client):
    document("AGM minutes 2026")
    html = client.get(reverse("portal:document_list")).content.decode()
    assert ">PIBG</h2>" in html
    assert "AGM minutes 2026" in html
