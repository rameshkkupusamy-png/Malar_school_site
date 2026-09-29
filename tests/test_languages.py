"""Tamil, Malay and English: Tamil first, a switcher, and posts in any of the three."""

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone, translation

from portal.models import Announcement, Event, EventImport, Subscriber
from portal.notifications import notify_subscribers


@pytest.fixture
def new_visitor(db):
    """Someone who has never picked a language (unlike the shared `client` fixture)."""
    return Client()


def test_first_visit_is_in_tamil_even_if_the_browser_prefers_malay(new_visitor):
    response = new_visitor.get(reverse("portal:home"), HTTP_ACCEPT_LANGUAGE="ms,en;q=0.8")

    page = response.content.decode()
    assert '<html lang="ta">' in page
    assert "செய்திகள்" in page  # "News" in the menu
    assert response["Content-Language"] == "ta"


def test_switcher_changes_the_language_and_remembers_it(new_visitor):
    response = new_visitor.post(
        reverse("set_language"), {"language": "ms", "next": reverse("portal:event_list")}
    )
    assert response.url == reverse("portal:event_list")

    page = new_visitor.get(reverse("portal:event_list")).content.decode()
    assert '<html lang="ms">' in page
    assert "Acara" in page and "Akan datang" in page

    new_visitor.post(reverse("set_language"), {"language": "en", "next": "/"})
    assert '<html lang="en">' in new_visitor.get("/").content.decode()


def test_unknown_language_cookie_falls_back_to_tamil(new_visitor, settings):
    new_visitor.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
    assert '<html lang="ta">' in new_visitor.get("/").content.decode()


def test_staff_pages_start_in_english(new_visitor):
    page = new_visitor.get(reverse("admin:login")).content.decode()
    assert 'lang="en"' in page


def test_post_shows_the_visitors_language_or_another_version(new_visitor):
    item = Announcement.objects.create(
        title_en="Sports day moved", body_en="It is now on Friday.", title_ta="விளையாட்டு நாள்"
    )

    tamil = new_visitor.get(item.get_absolute_url()).content.decode()
    assert "விளையாட்டு நாள்" in tamil
    assert "It is now on Friday." in tamil  # no Tamil text yet, so the English is shown

    new_visitor.post(reverse("set_language"), {"language": "en", "next": "/"})
    english = new_visitor.get(item.get_absolute_url()).content.decode()
    assert "Sports day moved" in english

    new_visitor.post(reverse("set_language"), {"language": "ms", "next": "/"})
    malay = new_visitor.get(item.get_absolute_url()).content.decode()
    assert "விளையாட்டு நாள்" in malay  # no Malay title: Tamil comes first in the fallbacks


@pytest.mark.django_db
def test_a_post_needs_a_title_in_at_least_one_language():
    empty = Announcement(body_ms="Isi")
    with pytest.raises(ValidationError) as error:
        empty.full_clean()
    assert "title_ta" in error.value.message_dict

    Announcement(title_ms="Tajuk", body_ms="Isi").full_clean()  # Malay alone is fine


@pytest.mark.django_db
def test_existing_english_posts_were_filed_under_english():
    # The data migration copied the old single-language text into the English fields.
    item = Announcement.objects.create(title_en="Old", body_en="Text")
    with translation.override("en"):
        assert Announcement.objects.get(pk=item.pk).title == "Old"


def test_parent_is_emailed_in_the_language_they_signed_up_in(new_visitor, settings):
    new_visitor.post(reverse("portal:subscribe"), {"email": "amma@example.com"})
    assert Subscriber.objects.get().language == "ta"

    event = Event.objects.create(
        title_ta="தீபாவளி கொண்டாட்டம்",
        title_en="Diwali celebration",
        starts_at="2030-10-23T09:00:00+08:00",
    )
    notify_subscribers(event)

    [message] = mail.outbox
    assert "தீபாவளி கொண்டாட்டம்" in message.subject
    assert "வணக்கம்" in message.body
    assert "Diwali" not in message.body


def test_malay_sign_up_gets_malay_emails(new_visitor):
    new_visitor.post(reverse("set_language"), {"language": "ms", "next": "/"})
    new_visitor.post(reverse("portal:subscribe"), {"email": "ibu@example.com"})

    event = Event.objects.create(title_en="Sports day", starts_at="2030-10-09T08:00:00+08:00")
    notify_subscribers(event)

    assert Subscriber.objects.get().language == "ms"
    assert "Salam sejahtera" in mail.outbox[0].body
    assert "Sports day" in mail.outbox[0].body  # no Malay title, so another version is used


def test_spreadsheet_text_is_saved_in_the_chosen_language(admin_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile(
        "acara.csv", b"Title,Start date,Location\nHari sukan,2030-10-09,Padang\n"
    )
    admin_client.post(reverse("admin:portal_event_import"), {"file": upload, "language": "ms"})

    event = Event.objects.get()
    assert event.title_ms == "Hari sukan" and event.location_ms == "Padang"
    assert not event.title_en and not event.title_ta
    assert EventImport.objects.get().language == "ms"


def test_event_times_read_naturally_in_each_language(new_visitor, make_event, settings):
    event = make_event("Sports day", days=3)
    event.starts_at = timezone.localtime(event.starts_at).replace(hour=15, minute=0)
    event.save()

    tamil = new_visitor.get(event.get_absolute_url()).content.decode()
    assert "பிற்பகல் 3:00" in tamil  # Tamil puts the part of day first

    new_visitor.cookies[settings.LANGUAGE_COOKIE_NAME] = "ms"
    malay = new_visitor.get(event.get_absolute_url()).content.decode()
    assert "3 ptg" in malay  # not Django's "3 malam" (3 at night)


@pytest.mark.parametrize("language", ["ta", "ms"])
def test_every_phrase_has_a_translation(language):
    from pathlib import Path

    from babel.messages.pofile import read_po

    path = Path(__file__).parent.parent / "locale" / language / "LC_MESSAGES" / "django.po"
    with path.open("rb") as handle:
        catalog = read_po(handle, locale=language)
    missing = [
        m.id
        for m in catalog
        if m.id and (m.fuzzy or not (all(m.string) if m.pluralizable else m.string))
    ]
    assert missing == [], "Run scripts/translations.py update, then translate these"
