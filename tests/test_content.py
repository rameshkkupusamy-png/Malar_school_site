from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from portal.models import Album, Announcement, Photo


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
