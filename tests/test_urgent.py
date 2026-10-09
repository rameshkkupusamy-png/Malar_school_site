from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from portal.models import UrgentNotice, end_of_today


@pytest.fixture
def notice(db):
    def _make(message="School closed today because of flooding.", **fields):
        """Pass message=None to set only the language fields (message_ta, message_ms, …)."""
        if message is not None:
            fields["message"] = message
        fields.setdefault("starts_at", timezone.now() - timedelta(hours=1))
        fields.setdefault("ends_at", timezone.now() + timedelta(hours=1))
        return UrgentNotice.objects.create(**fields)

    return _make


def test_showing_only_between_start_and_end_while_published(notice):
    now = timezone.now()
    current = notice("Now")
    notice("Later", starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2))
    notice("Over", starts_at=now - timedelta(hours=2), ends_at=now - timedelta(minutes=1))
    notice("Draft", is_published=False)

    assert list(UrgentNotice.objects.showing()) == [current]
    assert current not in UrgentNotice.objects.showing(now=current.ends_at)


def test_newest_notice_comes_first(notice):
    older = notice("Older", starts_at=timezone.now() - timedelta(hours=3))
    newer = notice("Newer", starts_at=timezone.now() - timedelta(minutes=5))
    assert list(UrgentNotice.objects.showing()) == [newer, older]


def test_default_end_is_the_end_of_today():
    end = timezone.localtime(end_of_today())
    assert end.date() == timezone.localdate()
    assert (end.hour, end.minute, end.second) == (23, 59, 59)
    assert UrgentNotice().ends_at == end_of_today()


@pytest.mark.django_db
def test_notice_must_end_after_it_starts():
    now = timezone.now()
    with pytest.raises(ValidationError) as error:
        UrgentNotice(message="x", starts_at=now, ends_at=now).full_clean()
    assert error.value.message_dict["ends_at"] == ["The notice must end after it starts."]


@pytest.mark.django_db
def test_notice_needs_a_message_in_one_language():
    with pytest.raises(ValidationError) as error:
        UrgentNotice(message="").full_clean()
    assert error.value.message_dict["message_ta"] == ["Write the notice in at least one language."]


@pytest.mark.django_db
def test_link_must_be_a_web_address():
    with pytest.raises(ValidationError) as error:
        UrgentNotice(message="x", link="javascript:alert(1)").full_clean()
    assert "link" in error.value.message_dict


def test_share_link_is_the_link_or_the_home_page(settings):
    settings.SITE_URL = "https://school.example"
    assert UrgentNotice(link="https://school.example/news/4/").share_link == (
        "https://school.example/news/4/"
    )
    assert UrgentNotice().share_link == "https://school.example/"


def test_bar_shows_on_every_page_with_details_link(notice, client):
    notice("Classes are online tomorrow because of haze.", link="https://school.example/news/4/")

    for url in (reverse("portal:home"), reverse("portal:event_list"), reverse("portal:contact")):
        html = client.get(url).content.decode()
        assert '<strong class="urgent-label">Urgent</strong>' in html
        assert "Classes are online tomorrow because of haze." in html
        assert '<a href="https://school.example/news/4/">Details</a>' in html


def test_no_bar_without_a_current_notice(notice, client):
    notice("Over", starts_at=timezone.now() - timedelta(hours=2), ends_at=timezone.now())
    assert 'class="urgent"' not in client.get(reverse("portal:home")).content.decode()


def test_message_falls_back_to_the_language_staff_wrote(notice, db):
    from django.test import Client

    notice(message=None, message_ms="Sekolah ditutup hari ini.")
    html = Client().get(reverse("portal:home")).content.decode()  # a Tamil visitor
    assert "Sekolah ditutup hari ini." in html
