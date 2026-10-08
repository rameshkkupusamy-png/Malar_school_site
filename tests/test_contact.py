import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from portal.models import SchoolContact, malaysian_number


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("03-8723 1234", "60387231234"),
        ("(03) 8723-1234", "60387231234"),
        ("012-345 6789", "60123456789"),
        ("+60 12-345 6789", "60123456789"),
        ("60123456789", "60123456789"),
        ("011-1234 5678", "601112345678"),
        ("06-123 4567", "6061234567"),
    ],
)
def test_malaysian_numbers_in_common_forms(typed, expected):
    assert malaysian_number(typed) == expected


@pytest.mark.parametrize(
    "typed", ["12345", "+65 9123 4567", "03-8723 12345678", "phone", "600123456"]
)
def test_other_numbers_are_refused(typed):
    with pytest.raises(ValueError):
        malaysian_number(typed)


@pytest.mark.django_db
def test_bad_number_gets_a_clear_message():
    with pytest.raises(ValidationError) as error:
        SchoolContact(phone="12345").full_clean()
    assert error.value.message_dict["phone"] == [
        "Enter a Malaysian phone number, for example 03-8723 1234 or 012-345 6789."
    ]


@pytest.mark.django_db
def test_map_link_must_be_a_web_address():
    with pytest.raises(ValidationError) as error:
        SchoolContact(map_url="javascript:alert(1)").full_clean()
    assert "map_url" in error.value.message_dict


def test_links():
    contact = SchoolContact(
        phone="03-8723 1234",
        whatsapp="012-345 6789",
        email="office@school.example",
        address="Lot 123, Jalan A & B #2, Semenyih",
    )
    assert contact.phone_link == "tel:+60387231234"
    assert contact.whatsapp_link == "https://wa.me/60123456789"
    assert contact.email_link == "mailto:office@school.example"
    query = "Lot%20123%2C%20Jalan%20A%20%26%20B%20%232%2C%20Semenyih"
    assert contact.google_maps_link == (f"https://www.google.com/maps/search/?api=1&query={query}")
    assert contact.waze_link == f"https://waze.com/ul?q={query}&navigate=yes"
    assert contact.can_visit and contact.has_details


def test_pasted_maps_link_wins_and_empty_record_has_nothing():
    assert SchoolContact(map_url="https://maps.app.goo.gl/abc").google_maps_link == (
        "https://maps.app.goo.gl/abc"
    )
    assert SchoolContact(map_url="https://maps.app.goo.gl/abc").waze_link == ""
    empty = SchoolContact()
    assert (empty.phone_link, empty.whatsapp_link, empty.google_maps_link) == ("", "", "")
    assert not empty.can_visit and not empty.has_details


@pytest.mark.django_db
def test_there_is_only_ever_one_record():
    assert SchoolContact.load().pk is None
    SchoolContact(email="a@school.example").save()
    SchoolContact(email="b@school.example").save()
    assert SchoolContact.objects.count() == 1
    assert SchoolContact.load().email == "b@school.example"


@pytest.mark.django_db
def test_page_shows_only_what_is_filled_in(client):
    SchoolContact(phone="03-8723 1234", email="office@school.example").save()

    html = client.get(reverse("portal:contact")).content.decode()

    assert 'href="tel:+60387231234"' in html and "Call the office" in html
    assert 'href="mailto:office@school.example"' in html
    assert "Message the office on WhatsApp" not in html
    assert "Open in Waze" not in html


@pytest.mark.django_db
def test_page_with_address_offers_directions_and_hours(client):
    SchoolContact(address="Jalan Semenyih,\n43500 Semenyih", hours_en="Mon–Fri 7.30–1.00").save()

    html = client.get(reverse("portal:contact")).content.decode()

    assert "Open in Google Maps" in html and "Open in Waze" in html
    assert "43500 Semenyih" in html
    assert "Mon–Fri 7.30–1.00" in html


@pytest.mark.django_db
def test_page_without_details_says_so(client):
    html = client.get(reverse("portal:contact")).content.decode()
    assert "Contact details will be added soon." in html


@pytest.mark.django_db
def test_footer_links_to_contact_page(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert f'href="{reverse("portal:contact")}"' in html


@pytest.mark.django_db
def test_admin_list_opens_the_form_then_the_record(admin_client):
    url = reverse("admin:portal_schoolcontact_changelist")
    assert admin_client.get(url)["Location"] == reverse("admin:portal_schoolcontact_add")

    SchoolContact(email="office@school.example").save()
    assert admin_client.get(url)["Location"] == reverse(
        "admin:portal_schoolcontact_change", args=[1]
    )
    assert admin_client.get(reverse("admin:portal_schoolcontact_add")).status_code == 403


@pytest.mark.django_db
def test_admin_saves_details_and_refuses_bad_numbers(admin_client):
    url = reverse("admin:portal_schoolcontact_add")
    response = admin_client.post(url, {"phone": "12345"})
    assert "Enter a Malaysian phone number" in response.content.decode()

    admin_client.post(url, {"phone": "03-8723 1234", "hours_ms": "Isnin–Jumaat"})
    assert SchoolContact.load().phone_link == "tel:+60387231234"


@pytest.mark.django_db
def test_contact_details_cannot_be_deleted(admin_client):
    SchoolContact(email="office@school.example").save()
    url = reverse("admin:portal_schoolcontact_delete", args=[1])
    assert admin_client.get(url).status_code == 403


@pytest.mark.django_db
def test_editors_can_edit_contact_details():
    call_command("setup_roles", stdout=None)
    codenames = set(
        Group.objects.get(name="Editors").permissions.values_list("codename", flat=True)
    )
    assert {"add_schoolcontact", "change_schoolcontact", "view_schoolcontact"} <= codenames
