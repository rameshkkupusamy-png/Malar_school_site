import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
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


def committee_rows(*members):
    data = {
        "committee-TOTAL_FORMS": str(len(members)),
        "committee-INITIAL_FORMS": "0",
        "committee-MIN_NUM_FORMS": "0",
        "committee-MAX_NUM_FORMS": "1000",
    }
    for index, (name, role) in enumerate(members):
        data |= {
            f"committee-{index}-name": name,
            f"committee-{index}-role": role,
            f"committee-{index}-order": "0",
        }
    return data


@pytest.mark.django_db
def test_admin_list_opens_the_form_then_the_record(admin_client):
    url = reverse("admin:portal_pibg_changelist")
    assert admin_client.get(url)["Location"] == reverse("admin:portal_pibg_add")

    Pibg(term="2026/2027").save()
    assert admin_client.get(url)["Location"] == reverse("admin:portal_pibg_change", args=[1])


@pytest.mark.django_db
def test_admin_saves_the_term_and_committee(admin_client):
    data = {"term": "2026/2027", "about_en": "Yearly fee RM20."}
    data |= committee_rows(("Encik Arun", "chair"), ("Puan Kavitha", "treasurer"))

    response = admin_client.post(reverse("admin:portal_pibg_add"), data)

    assert response["Location"] == reverse("admin:portal_pibg_change", args=[1])
    pibg = Pibg.load()
    assert pibg.term == "2026/2027"
    assert [m.name for m in pibg.members()] == ["Encik Arun", "Puan Kavitha"]


@pytest.mark.django_db
def test_admin_refuses_a_bad_phone(admin_client):
    data = {"phone": "12345"} | committee_rows()
    response = admin_client.post(reverse("admin:portal_pibg_add"), data)
    assert "Enter a Malaysian phone number" in response.content.decode()
    assert not Pibg.objects.exists()


@pytest.mark.django_db
def test_admin_warns_that_names_are_public(admin_client):
    html = admin_client.get(reverse("admin:portal_pibg_add")).content.decode()
    assert "Add only people who agreed to be listed." in html


@pytest.mark.django_db
def test_pibg_record_cannot_be_deleted(admin_client):
    Pibg(term="2026/2027").save()
    url = reverse("admin:portal_pibg_delete", args=[1])
    assert admin_client.get(url).status_code == 403


@pytest.mark.django_db
def test_add_page_goes_to_the_record_once_it_exists(admin_client):
    Pibg(term="2026/2027").save()
    response = admin_client.get(reverse("admin:portal_pibg_add"))
    assert response["Location"] == reverse("admin:portal_pibg_change", args=[1])


@pytest.mark.django_db
def test_save_and_add_another_goes_to_the_record(admin_client):
    data = {"term": "2026/2027", "_addanother": "Save and add another"} | committee_rows()
    response = admin_client.post(reverse("admin:portal_pibg_add"), data)
    assert response["Location"] == reverse("admin:portal_pibg_change", args=[1])


@pytest.mark.django_db
def test_editor_can_set_up_pibg_and_its_committee(client):
    call_command("setup_roles", stdout=None)
    editor = User.objects.create_user("editor", password="x", is_staff=True)
    editor.groups.add(Group.objects.get(name="Editors"))
    client.force_login(editor)

    data = {"term": "2026/2027"} | committee_rows(("Puan Kavitha", "treasurer"))
    client.post(reverse("admin:portal_pibg_add"), data)

    assert [m.name for m in Pibg.load().members()] == ["Puan Kavitha"]
    page = client.get(reverse("admin:portal_pibg_change", args=[1]))
    assert page.status_code == 200
