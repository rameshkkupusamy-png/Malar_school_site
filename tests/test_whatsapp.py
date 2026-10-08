from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.models import Announcement
from portal.whatsapp import share_message, share_url


def shared_text(url):
    parsed = urlparse(url)
    assert parsed.netloc == "wa.me"
    return parse_qs(parsed.query)["text"][0]


def test_event_message_has_title_time_place_and_link(make_event, settings):
    settings.SITE_URL = "https://school.example"
    event = make_event("Sports day", location="School field")

    text = shared_text(share_url(event))

    assert text.startswith("*Sports day*")
    assert "School field" in text
    assert f"https://school.example/events/{event.pk}/" in text
    assert text == share_message(event)


@pytest.mark.django_db
def test_news_message_shortens_long_text(settings):
    settings.SITE_URL = "https://school.example"
    post = Announcement.objects.create(title="Holiday", body="word " * 100)

    text = share_message(post)

    assert text.startswith("*Holiday*")
    assert text.count("word") == 40
    assert f"https://school.example/news/{post.pk}/" in text


def test_message_uses_language_the_post_was_written_in(make_event):
    event = make_event(title_ta="", title_en="Open day")
    assert share_message(event).startswith("*Open day*")


def test_event_list_shows_share_button_only_for_published(make_event, admin_client):
    shown = make_event("Science fair")
    make_event("Draft trip", is_published=False)

    html = admin_client.get(reverse("admin:portal_event_changelist")).content.decode()

    assert html.count("Share on WhatsApp") == 1
    assert "https://wa.me/?text=" in html
    assert "Not shown to parents yet" in html
    assert shown.title in html


@pytest.mark.django_db
def test_scheduled_news_cannot_be_shared_yet(admin_client):
    post = Announcement.objects.create(
        title="Next term", body="Soon", published_at=timezone.now() + timedelta(days=1)
    )

    url = reverse("admin:portal_announcement_change", args=[post.pk])
    html = admin_client.get(url).content.decode()

    assert "Share on WhatsApp" not in html
    assert "Not shown to parents yet" in html


@pytest.mark.django_db
def test_new_news_form_asks_to_publish_first(admin_client):
    html = admin_client.get(reverse("admin:portal_announcement_add")).content.decode()
    assert "Save and publish first" in html
