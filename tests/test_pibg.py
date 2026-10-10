from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from portal.models import CommitteeMember, Document, Event, Pibg
from portal.search import find


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


def pibg_page(client):
    return client.get(reverse("portal:pibg"))


@pytest.mark.django_db
def test_page_before_set_up_says_details_coming_soon(client):
    html = pibg_page(client).content.decode()
    assert "Details coming soon." in html
    assert "Committee" not in html


@pytest.mark.django_db
def test_page_shows_about_contact_and_committee_in_order(client):
    pibg = Pibg.objects.create(
        term="2026/2027",
        about_en="Yearly fee RM20.\n\nPay at the office.",
        phone="012-345 6789",
        whatsapp_group="https://chat.whatsapp.com/abc",
    )
    pibg.committee.create(name="Puan Kavitha", role=CommitteeMember.TREASURER)
    pibg.committee.create(name="Encik Arun", role=CommitteeMember.CHAIR)

    html = pibg_page(client).content.decode()

    assert "Details coming soon." not in html
    assert "Yearly fee RM20." in html
    assert 'href="tel:+60123456789"' in html and "Call PIBG" in html
    assert 'href="https://chat.whatsapp.com/abc"' in html
    assert "Join the PIBG WhatsApp group" in html
    assert "Email PIBG" not in html
    assert "Committee for 2026/2027" in html
    assert html.index("Encik Arun") < html.index("Puan Kavitha")
    assert "Chairperson" in html and "Treasurer" in html


@pytest.mark.django_db
def test_committee_heading_without_a_term(client):
    Pibg.objects.create().committee.create(name="Encik Arun", role=CommitteeMember.CHAIR)
    assert ">Committee</h2>" in pibg_page(client).content.decode()


@pytest.mark.django_db
def test_upcoming_meetings_are_published_pibg_events_only(client, make_event):
    make_event("PIBG AGM", days=5, kind=Event.PIBG)
    make_event("Hidden PIBG meeting", days=6, kind=Event.PIBG, is_published=False)
    make_event("Sports day", days=7)

    response = pibg_page(client)
    html = response.content.decode()

    assert [e.title for e in response.context["upcoming"]] == ["PIBG AGM"]
    assert "Hidden PIBG meeting" not in html
    assert "Sports day" not in html
    assert f'href="{reverse("portal:event_list")}?type=pibg"' in html


@pytest.mark.django_db
def test_past_meetings_are_the_newest_five(client, make_event):
    for day in range(1, 8):
        make_event(f"Meeting {day}", days=-day, kind=Event.PIBG)
    titles = [e.title for e in pibg_page(client).context["past"]]
    assert titles == ["Meeting 1", "Meeting 2", "Meeting 3", "Meeting 4", "Meeting 5"]


@pytest.mark.django_db
def test_documents_are_published_unexpired_pibg_ones(client):
    document("AGM minutes 2026")
    document("Draft minutes", is_published=False)
    document("Old fee notice", remove_after=timezone.localdate() - timedelta(days=1))
    document("Booklist", group=Document.LIST)

    response = pibg_page(client)

    assert [d.title for d in response.context["documents"]] == ["AGM minutes 2026"]
    assert "Minutes and circulars" in response.content.decode()


@pytest.mark.django_db
def test_page_is_not_indexed_and_linked_from_menu_and_footer(client):
    html = pibg_page(client).content.decode()
    assert '<meta name="robots" content="noindex">' in html
    assert f'<a href="{reverse("portal:pibg")}" aria-current="page">PIBG</a>' in html
    home = client.get(reverse("portal:home")).content.decode()
    assert home.count(f'href="{reverse("portal:pibg")}"') == 2


@pytest.mark.django_db
def test_committee_names_are_not_searchable():
    Pibg.objects.create().committee.create(name="Puan Kavitha Raman", role=CommitteeMember.CHAIR)
    assert find("Kavitha") == []
