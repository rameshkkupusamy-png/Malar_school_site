import re
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import translation
from PIL import Image

from portal.models import Achievement, AchievementPhoto, AchievementPupil, short_name
from portal.whatsapp import share_message


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"


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
        ("Nur Aisyah bt. Ahmad", "Nur Aisyah A."),
        ("Ali Bin. Abu", "Ali A."),
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

    photo = item.photos.get()
    for url in (reverse("portal:achievement_list"), item.get_absolute_url()):
        html = client.get(url).content.decode()
        assert photo.image.url not in html
        assert "Kavin R. (5 Mutiara)" in html
        assert "Meera" not in html
        assert "a Year 5 pupil" in html

    item.pupils.update(consent=True)
    assert photo.image.url in client.get(item.get_absolute_url()).content.decode()


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


def test_whatsapp_message_uses_displayed_names_only(achievement, settings):
    settings.SITE_URL = "https://school.example"
    item = achievement(
        pupils=[("Kavin a/l Raju", "5 Mutiara", True), ("Meera a/p Suresh", "5 Mutiara", False)]
    )

    text = share_message(item)

    assert text.startswith("*1st place, district Tamil essay competition*\nKavin R. (5 Mutiara), ")
    assert "Raju" not in text and "Meera" not in text
    assert text.endswith(f"https://school.example/achievements/{item.pk}/")


def test_admin_list_shows_consent_summary(achievement, admin_client):
    achievement(pupils=[("Kavin a/l Raju", "5 Mutiara", True), ("Meera", "5 Mutiara", False)])
    html = admin_client.get(reverse("admin:portal_achievement_changelist")).content.decode()
    assert "1 of 2 agreed" in html


def test_admin_warns_when_photos_are_held_back(achievement, admin_client):
    item = achievement(pupils=[("Meera", "5 Mutiara", False)])
    html = admin_client.get(
        reverse("admin:portal_achievement_change", args=[item.pk])
    ).content.decode()
    assert "Photos are hidden until every pupil" in html


@pytest.mark.django_db
def test_editor_can_add_an_achievement_with_pupils_and_photos(client):
    call_command("setup_roles", stdout=None)
    editor = User.objects.create_user("editor", password="x", is_staff=True)
    editor.groups.add(Group.objects.get(name="Editors"))
    client.force_login(editor)

    response = client.post(
        reverse("admin:portal_achievement_add"),
        {
            "title_ta": "மாவட்ட கட்டுரைப் போட்டியில் முதல் பரிசு",
            "date": "2026-09-12",
            "category": Achievement.TAMIL,
            "level": Achievement.DISTRICT,
            "is_published": "on",
            "pupils-TOTAL_FORMS": "1",
            "pupils-INITIAL_FORMS": "0",
            "pupils-MIN_NUM_FORMS": "0",
            "pupils-MAX_NUM_FORMS": "1000",
            "pupils-0-name": "Kavin a/l Raju",
            "pupils-0-class_name": "5 Mutiara",
            "pupils-0-consent": "on",
            "photos-TOTAL_FORMS": "1",
            "photos-INITIAL_FORMS": "0",
            "photos-MIN_NUM_FORMS": "0",
            "photos-MAX_NUM_FORMS": "1000",
            "photos-0-image": jpeg(),
            "photos-0-order": "0",
        },
    )

    assert response.status_code == 302, response.content.decode()[-3000:]
    item = Achievement.objects.get()
    assert item.pupils.get().consent
    assert item.photos.count() == 1


# Photo files: private, random names, served only through the consent gate ------------------


def test_photo_files_get_random_names_outside_the_public_media_folder(achievement, settings):
    photo = AchievementPhoto.objects.create(
        achievement=achievement(),
        image=SimpleUploadedFile("Kavin Raju 1st place.jpg", jpeg().read()),
    )

    assert re.fullmatch(r"achievements/[0-9a-f]{32}\.jpg", photo.image.name)
    assert Path(photo.image.path).is_relative_to(settings.PRIVATE_MEDIA_ROOT)
    assert not (Path(settings.MEDIA_ROOT) / photo.image.name).exists()


def test_photo_is_served_only_while_published_with_everyone_agreed(achievement, client):
    item = achievement(pupils=[("Kavin a/l Raju", "5 Mutiara", True)])
    photo = AchievementPhoto.objects.create(achievement=item, image=jpeg())
    url = photo.image.url

    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert "no-store" in response["Cache-Control"]
    assert response["X-Robots-Tag"] == "noindex"
    assert b"".join(response.streaming_content)[:2] == bytes([0xFF, 0xD8])  # a JPEG

    item.pupils.update(consent=False)  # a parent withdrew consent
    assert client.get(url).status_code == 404

    item.pupils.update(consent=True)
    Achievement.objects.filter(pk=item.pk).update(is_published=False)
    assert client.get(url).status_code == 404


def test_staff_can_see_held_back_photos(achievement, admin_client):
    item = achievement(pupils=[("Meera", "5 Mutiara", False)])
    photo = AchievementPhoto.objects.create(achievement=item, image=jpeg())
    assert admin_client.get(photo.image.url).status_code == 200


@pytest.mark.django_db
def test_unknown_private_file_is_not_found(client):
    assert (
        client.get("/private/achievements/0123456789abcdef0123456789abcdef.jpg").status_code == 404
    )
    assert client.get("/private/../db.sqlite3").status_code == 404


def test_deleting_photos_or_achievements_deletes_the_files(
    achievement, django_capture_on_commit_callbacks
):
    item = achievement()
    first = AchievementPhoto.objects.create(achievement=item, image=jpeg())
    second = AchievementPhoto.objects.create(achievement=item, image=jpeg())
    first_path, second_path = Path(first.image.path), Path(second.image.path)

    with django_capture_on_commit_callbacks(execute=True):
        first.delete()
    assert not first_path.exists()

    with django_capture_on_commit_callbacks(execute=True):
        item.delete()
    assert not second_path.exists()


def test_replacing_a_photo_deletes_the_old_file(achievement, django_capture_on_commit_callbacks):
    photo = AchievementPhoto.objects.create(achievement=achievement(), image=jpeg())
    old_path = Path(photo.image.path)

    with django_capture_on_commit_callbacks(execute=True):
        photo.image = jpeg((800, 600))
        photo.save()

    assert not old_path.exists()
    assert Path(photo.image.path).exists()


# Admin warnings and other review fixes --------------------------------------------------------


def test_admin_warns_when_photos_show_without_pupils_listed(achievement, admin_client):
    item = achievement("Gold, state choir competition")
    html = admin_client.get(
        reverse("admin:portal_achievement_change", args=[item.pk])
    ).content.decode()
    assert "No pupils are listed, so these photos are shown" in html


def test_admin_note_mentions_unpublished(achievement, admin_client):
    item = achievement(pupils=[("Kavin a/l Raju", "5 Mutiara", True)], is_published=False)
    html = admin_client.get(
        reverse("admin:portal_achievement_change", args=[item.pk])
    ).content.decode()
    assert "not published, so nothing is shown yet" in html


@pytest.mark.parametrize("query", ["?year=²", "?year=" + "9" * 5000, "?year=-1"])
def test_odd_year_values_do_not_break_the_page(achievement, client, query):
    achievement("Choir", date=date(2026, 3, 1))
    response = page(client, query)
    assert response.status_code == 200
    assert response.context["year"] == 2026


def test_titles_and_captions_warn_against_full_names():
    for model, field in [(Achievement, "title"), (AchievementPhoto, "caption")]:
        assert "full names" in str(model._meta.get_field(field).help_text)
