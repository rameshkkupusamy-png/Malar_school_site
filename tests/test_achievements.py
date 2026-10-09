from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import translation
from PIL import Image

from portal.models import Achievement, AchievementPhoto, AchievementPupil, short_name


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def jpeg(size=(3000, 2000)):
    out = BytesIO()
    Image.new("RGB", size, (30, 60, 200)).save(out, "JPEG")
    return SimpleUploadedFile("win.jpg", out.getvalue())


@pytest.fixture
def achievement(db):
    def _make(title="1st place, district Tamil essay competition", pupils=(), **fields):
        fields.setdefault("date", date(2026, 9, 12))
        fields.setdefault("category", Achievement.TAMIL)
        fields.setdefault("level", Achievement.DISTRICT)
        item = Achievement.objects.create(title=title, **fields)
        for name, class_name, consent, *full in pupils:
            item.pupils.create(
                name=name, class_name=class_name, consent=consent, show_full_name=bool(full)
            )
        return item

    return _make


@pytest.mark.parametrize(
    ("full", "short"),
    [
        ("Kavin a/l Raju", "Kavin R."),
        ("Kavin  A/L raju", "Kavin R."),
        ("Meera a/p Suresh", "Meera S."),
        ("Nur Aisyah binti Ahmad", "Nur Aisyah A."),
        ("Muhammad Danial bin Ismail", "Muhammad Danial I."),
        ("Meera Suresh", "Meera S."),
        ("Tharshini", "Tharshini"),
        ("  ", ""),
    ],
)
def test_short_name(full, short):
    assert short_name(full) == short


def test_pupil_display_follows_consent_and_full_name_choice():
    with translation.override("en"):
        assert AchievementPupil(
            name="Kavin a/l Raju", class_name="5 Mutiara", consent=True
        ).display == ("Kavin R. (5 Mutiara)")
        assert (
            AchievementPupil(name="Kavin a/l Raju", class_name="", consent=True).display
            == "Kavin R."
        )
        assert (
            AchievementPupil(
                name="Kavin a/l Raju", class_name="5 Mutiara", consent=True, show_full_name=True
            ).display
            == "Kavin a/l Raju (5 Mutiara)"
        )
        assert AchievementPupil(name="Kavin a/l Raju", class_name="5 Mutiara").display == (
            "a Year 5 pupil"
        )
        assert AchievementPupil(name="Kavin a/l Raju", class_name="Mutiara").display == "a pupil"


def test_photos_need_every_pupil_to_have_consent(achievement):
    agreed = achievement(pupils=[("Kavin a/l Raju", "5 Mutiara", True)])
    mixed = achievement(
        pupils=[("Kavin a/l Raju", "5 Mutiara", True), ("Meera a/p Suresh", "5 Mutiara", False)]
    )
    team = achievement("Gold, state choir competition")

    assert agreed.photos_allowed
    assert not mixed.photos_allowed
    assert team.photos_allowed
    assert mixed.consent_summary == "1 of 2 agreed"
    assert agreed.consent_summary == "all agreed"
    assert team.consent_summary == "no pupils listed"


def test_pupil_line_and_levels(achievement):
    item = achievement(
        level=Achievement.STATE,
        pupils=[("Kavin a/l Raju", "5 Mutiara", True), ("Meera a/p Suresh", "5 Mutiara", False)],
    )
    with translation.override("en"):
        assert item.pupil_line == "Kavin R. (5 Mutiara), a Year 5 pupil"
    assert item.is_high_level
    assert not achievement(level=Achievement.DISTRICT).is_high_level


def test_photos_are_shrunk_on_upload(achievement):
    photo = AchievementPhoto.objects.create(achievement=achievement(), image=jpeg())
    assert photo.image.name.startswith("achievements/")
    assert Image.open(photo.image.path).size == (2000, 1333)


def test_published_hides_drafts(achievement):
    shown = achievement()
    achievement("Draft", is_published=False)
    assert list(Achievement.objects.published()) == [shown]


def page(client, query=""):
    return client.get(reverse("portal:achievement_list") + query)


def test_page_opens_on_the_latest_year_with_links_to_others(achievement, client):
    achievement("Older win", date=date(2025, 6, 1))
    achievement("Newer win", date=date(2026, 3, 1))

    response = page(client)

    assert response.context["year"] == 2026
    assert [a.title for a in response.context["achievements"]] == ["Newer win"]
    html = response.content.decode()
    assert 'href="?year=2025"' in html
    assert '<meta name="robots" content="noindex">' in html


def test_year_and_filter_query(achievement, client):
    achievement("Essay", date=date(2025, 6, 1), category=Achievement.TAMIL)
    achievement("Relay", date=date(2025, 7, 1), category=Achievement.SPORTS)
    achievement("Choir", date=date(2026, 3, 1), category=Achievement.ARTS)

    response = page(client, "?year=2025&type=sports")
    assert [a.title for a in response.context["achievements"]] == ["Relay"]
    assert 'href="?year=2025&amp;type=tamil"' in response.content.decode()

    # Sports has nothing in 2026, so the page falls back to Sports' latest year.
    response = page(client, "?year=2026&type=sports")
    assert response.context["year"] == 2025


@pytest.mark.parametrize("query", ["?year=junk", "?year=1999", "?type=nonsense"])
def test_bad_query_values_fall_back(achievement, client, query):
    achievement("Choir", date=date(2026, 3, 1))
    assert page(client, query).context["year"] == 2026


@pytest.mark.django_db
def test_empty_page_says_so(client):
    assert "No achievements yet." in page(client).content.decode()


def test_photos_hidden_until_every_pupil_agreed(achievement, client):
    item = achievement(
        pupils=[("Kavin a/l Raju", "5 Mutiara", True), ("Meera a/p Suresh", "5 Mutiara", False)]
    )
    AchievementPhoto.objects.create(achievement=item, image=jpeg())

    for url in (reverse("portal:achievement_list"), item.get_absolute_url()):
        html = client.get(url).content.decode()
        assert "achievements/win" not in html
        assert "Kavin R. (5 Mutiara)" in html
        assert "Meera" not in html
        assert "a Year 5 pupil" in html

    item.pupils.update(consent=True)
    assert "achievements/win" in client.get(item.get_absolute_url()).content.decode()


def test_detail_page_and_drafts(achievement, client):
    shown = achievement(description="Well done!")
    draft = achievement("Draft", is_published=False)

    html = client.get(shown.get_absolute_url()).content.decode()
    assert "Well done!" in html
    assert '<meta name="robots" content="noindex">' in html
    assert client.get(draft.get_absolute_url()).status_code == 404


def test_high_level_wins_are_highlighted(achievement, client):
    achievement("State gold", level=Achievement.STATE)
    achievement("District silver", level=Achievement.DISTRICT)
    html = page(client).content.decode()
    assert '<span class="level level--high">State</span>' in html
    assert '<span class="level">District</span>' in html


@pytest.mark.django_db
def test_menu_links_to_achievements(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert html.count(f'href="{reverse("portal:achievement_list")}"') == 2  # menu and footer
