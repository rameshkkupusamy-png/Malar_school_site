from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from portal.models import Album, Announcement, Event, Photo


@pytest.mark.django_db
def test_news_hides_scheduled_and_unpublished_and_puts_pinned_first(client):
    now = timezone.now()
    Announcement.objects.create(title="Older", body="x", published_at=now - timedelta(days=2))
    Announcement.objects.create(
        title="Pinned", body="x", is_pinned=True, published_at=now - timedelta(days=5)
    )
    Announcement.objects.create(title="Scheduled", body="x", published_at=now + timedelta(days=1))
    Announcement.objects.create(title="Draft", body="x", is_published=False)

    response = client.get(reverse("portal:announcement_list"))

    assert [a.title for a in response.context["page"]] == ["Pinned", "Older"]


@pytest.mark.django_db
def test_scheduled_announcement_detail_is_404(client):
    item = Announcement.objects.create(
        title="Later", body="x", published_at=timezone.now() + timedelta(days=1)
    )
    assert client.get(item.get_absolute_url()).status_code == 404


@pytest.mark.django_db
def test_gallery_lists_published_albums_only(client):
    Album.objects.create(title="Sports day photos")
    Album.objects.create(title="Private", is_published=False)

    response = client.get(reverse("portal:album_list"))

    assert [a.title for a in response.context["page"]] == ["Sports day photos"]


@pytest.mark.django_db
def test_album_detail_shows_photos(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    album = Album.objects.create(title="Trip")
    Photo.objects.create(album=album, image="gallery/a.jpg", caption="At the museum")

    response = client.get(album.get_absolute_url())

    assert b"At the museum" in response.content


@pytest.mark.django_db
def test_setup_roles_creates_editors_group():
    call_command("setup_roles")
    group = Group.objects.get(name="Editors")
    codenames = set(group.permissions.values_list("codename", flat=True))
    assert "add_event" in codenames
    assert "view_subscriber" in codenames
    assert "delete_subscriber" not in codenames


@pytest.mark.django_db
def test_home_photos_use_the_next_event_picture_then_the_newest_album(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    album = Album.objects.create(title="Sports day photos")
    Photo.objects.create(album=album, image="gallery/a.jpg", caption="Credit A", order=0)
    Photo.objects.create(album=album, image="gallery/b.jpg", order=1)
    Album.objects.create(title="Empty album")  # newer, but no photos to show

    response = client.get(reverse("portal:home"))
    assert response.context["hero_image"].name == "gallery/a.jpg"
    assert response.context["hero_credit"] == "Credit A"
    assert response.context["featured_album"] == album
    assert response.context["band_photo"].image.name == "gallery/b.jpg"

    Event.objects.create(
        title="Science fair", starts_at=timezone.now() + timedelta(days=2), image="events/fair.jpg"
    )
    response = client.get(reverse("portal:home"))
    assert response.context["hero_image"].name == "events/fair.jpg"
    assert response.context["hero_credit"] is None
    assert response.context["band_photo"].image.name == "gallery/a.jpg"


@pytest.mark.django_db
def test_home_skips_unpublished_albums_for_photos(client):
    hidden = Album.objects.create(title="Private", is_published=False)
    Photo.objects.create(album=hidden, image="gallery/secret.jpg")

    response = client.get(reverse("portal:home"))

    assert response.context["hero_image"] is None
    assert response.context["featured_album"] is None
    assert b"secret.jpg" not in response.content
