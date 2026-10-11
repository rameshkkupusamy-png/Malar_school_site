import io
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from portal.models import (
    Achievement,
    Album,
    Announcement,
    Document,
    Event,
    Photo,
    SiteSections,
    Subscriber,
)
from portal.notifications import notify_subscribers, send_reminders
from portal.search import find
from portal.whatsapp import is_public

KEYS = ["news", "events", "photos", "documents", "pibg", "achievements", "search"]


def pause(*keys):
    record = SiteSections.load()
    for key in keys:
        setattr(record, key, False)
    record.save()


@pytest.mark.django_db
def test_every_section_is_on_before_anyone_saves():
    record = SiteSections.load()
    assert record.pk is None
    assert all(getattr(record, key) for key in KEYS)


@pytest.mark.django_db
def test_there_is_only_ever_one_record():
    SiteSections(news=False).save()
    SiteSections(events=False).save()
    assert SiteSections.objects.count() == 1
    assert SiteSections.load().events is False


@pytest.mark.django_db
def test_superuser_can_pause_a_section(admin_client):
    data = {key: "on" for key in KEYS if key != "photos"}
    response = admin_client.post(reverse("admin:portal_sitesections_add"), data)
    assert response["Location"] == reverse("admin:portal_sitesections_change", args=[1])
    assert SiteSections.load().photos is False
    assert SiteSections.load().news is True


@pytest.mark.django_db
def test_admin_explains_what_pausing_events_stops(admin_client):
    html = admin_client.get(reverse("admin:portal_sitesections_add")).content.decode()
    assert "Also stops email sign-ups, event emails and reminders." in html


@pytest.mark.django_db
def test_site_sections_cannot_be_deleted(admin_client):
    SiteSections().save()
    url = reverse("admin:portal_sitesections_delete", args=[1])
    assert admin_client.get(url).status_code == 403


def editor(client, *extra_permissions):
    call_command("setup_roles", stdout=None)
    user = User.objects.create_user("editor", password="x", is_staff=True)
    user.groups.add(Group.objects.get(name="Editors"))
    user.user_permissions.add(*Permission.objects.filter(codename__in=extra_permissions))
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_editors_cannot_see_or_open_site_sections(client):
    editor(client)
    SiteSections().save()
    assert "Site sections" not in client.get(reverse("admin:index")).content.decode()
    url = reverse("admin:portal_sitesections_change", args=[1])
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_editor_given_the_permission_by_hand_still_cannot_open_it(client):
    editor(client, "view_sitesections", "change_sitesections", "add_sitesections")
    assert client.get(reverse("admin:portal_sitesections_add")).status_code == 403
    SiteSections().save()
    url = reverse("admin:portal_sitesections_change", args=[1])
    assert client.get(url).status_code == 403


@pytest.fixture
def content(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    event = Event.objects.create(title="Sports day", starts_at=timezone.now() + timedelta(days=3))
    news = Announcement.objects.create(title="Sports day news", body="x")
    album = Album.objects.create(title="Sports day photos", event=event)
    document = Document.objects.create(
        title="Sports day form", file=SimpleUploadedFile("form.pdf", b"%PDF-1.4")
    )
    achievement = Achievement.objects.create(
        title="Sports day gold",
        category=Achievement.CATEGORIES[0][0],
        level=Achievement.LEVELS[0][0],
    )
    return {
        "news": ["/news/", f"/news/{news.pk}/"],
        "events": [
            "/events/",
            f"/events/{event.pk}/",
            f"/events/{event.pk}/calendar.ics",
            "/events/calendar.ics",
        ],
        "photos": ["/gallery/", f"/gallery/{album.pk}/"],
        "documents": ["/documents/", f"/documents/{document.pk}/"],
        "pibg": ["/pibg/"],
        "achievements": ["/achievements/", f"/achievements/{achievement.pk}/"],
        "search": ["/search/?q=sports"],
    }


@pytest.mark.django_db
def test_every_section_page_opens_by_default(client, content):
    for paths in content.values():
        for path in paths:
            assert client.get(path).status_code < 400, path


@pytest.mark.parametrize("key", KEYS)
def test_paused_section_shows_the_paused_page_and_others_still_open(client, content, key):
    pause(key)
    for path in content[key]:
        response = client.get(path)
        html = response.content.decode()
        assert response.status_code == 503, path
        assert "This section is not available right now" in html
        assert '<meta name="robots" content="noindex">' in html
        assert 'href="/contact/"' in html
    for other, paths in content.items():
        if other != key:
            for path in paths:
                assert client.get(path).status_code < 400, path


@pytest.mark.django_db
def test_paused_detail_link_that_never_existed_is_still_paused(client):
    pause("news", "achievements")
    assert client.get("/news/99999/").status_code == 503
    assert client.get("/private/achievements/nothing.jpg").status_code == 503


@pytest.mark.django_db
def test_switching_a_section_back_on_restores_it(client, content):
    pause("news")
    assert client.get("/news/").status_code == 503
    record = SiteSections.load()
    record.news = True
    record.save()
    assert client.get("/news/").status_code == 200


@pytest.mark.django_db
def test_paused_events_refuse_new_sign_ups(client):
    pause("events")
    response = client.post(reverse("portal:subscribe"), {"email": "parent@example.com"})
    assert response.status_code == 503
    assert not Subscriber.objects.exists()


def test_unknown_section_key_is_a_mistake():
    from portal.sections import section

    with pytest.raises(ValueError):
        section("newz")


MENU = {
    "news": "/news/",
    "events": "/events/",
    "photos": "/gallery/",
    "documents": "/documents/",
    "pibg": "/pibg/",
    "achievements": "/achievements/",
    "search": "/search/",
}


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.django_db
def test_paused_section_leaves_the_menu_and_footer(client, key):
    contact = client.get(reverse("portal:contact")).content.decode()
    assert contact.count(f'href="{MENU[key]}"') == 2
    pause(key)
    contact = client.get(reverse("portal:contact")).content.decode()
    assert f'href="{MENU[key]}"' not in contact


@pytest.mark.django_db
def test_menu_is_complete_on_the_search_page(client):
    html = client.get("/search/?q=sports").content.decode()
    assert 'href="/news/"' in html


@pytest.mark.django_db
def test_home_without_news(client, content):
    pause("news")
    html = client.get("/").content.decode()
    assert "Sports day news" not in html
    assert "All news" not in html
    assert "Sports day" in html  # the next event leads instead


@pytest.mark.django_db
def test_home_without_events_has_no_events_or_sign_up(client, content):
    pause("events", "news")
    html = client.get("/").content.decode()
    assert "Coming up" not in html
    assert 'action="/subscribe/"' not in html
    assert "Get event emails" not in html
    assert "/events/" not in html


@pytest.mark.django_db
def test_home_without_photos_uses_no_album(client, content):
    add_photo()
    assert "See the photos" in client.get("/").content.decode()
    pause("photos")
    html = client.get("/").content.decode()
    assert "See the photos" not in html
    assert "/gallery/" not in html


def add_photo():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(buffer, "JPEG")  # Photo.save() shrinks it
    image = SimpleUploadedFile("a.jpg", buffer.getvalue())
    Photo.objects.create(album=Album.objects.get(), image=image)


@pytest.mark.django_db
def test_home_with_everything_paused_is_just_the_welcome(client, content):
    add_photo()
    pause(*KEYS)
    response = client.get("/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "Welcome to" in html
    assert "band--album" not in html
    assert 'class="band-img"' not in html
    for path in MENU.values():
        assert f'href="{path}' not in html


@pytest.mark.django_db
def test_welcome_line_does_not_name_sections(client, content):
    pause(*KEYS)
    html = client.get("/").content.decode()
    assert "Updates from school, for parents and guardians." in html
    assert "News, events and photos" not in html


# The rounded line runs from band to band; it must end inside the page, not at the footer.
HERO_DOWN = '<div class="band-frame band-frame--down"'
HERO_END = '<div class="band-frame" aria-hidden'
ALBUM_DOWN = '<div class="band-frame band-frame--up band-frame--down"'
ALBUM_END = '<div class="band-frame band-frame--up" aria-hidden'


@pytest.mark.django_db
def test_line_runs_through_every_part_when_all_is_on(client, content):
    add_photo()
    html = client.get("/").content.decode()
    assert HERO_DOWN in html
    assert ALBUM_DOWN in html
    assert "split--end" not in html


@pytest.mark.django_db
def test_line_ends_at_the_album_while_events_are_paused(client, content):
    add_photo()
    pause("events")
    html = client.get("/").content.decode()
    assert HERO_DOWN in html
    assert ALBUM_END in html
    assert "split--end" not in html


@pytest.mark.django_db
def test_line_ends_in_the_news_part_when_it_is_last(client, content):
    pause("events")
    html = client.get("/").content.decode()
    assert HERO_DOWN in html
    assert 'class="split split--end wrap"' in html


@pytest.mark.django_db
def test_line_ends_at_the_top_band_when_nothing_follows(client, content):
    pause(*KEYS)
    html = client.get("/").content.decode()
    assert HERO_END in html
    assert HERO_DOWN not in html


def site_sections_reads(client, url):
    with CaptureQueriesContext(connection) as queries:
        client.get(url)
    # Reads of the record itself; the admin sidebar's "does it exist yet?" check doesn't count.
    reads = [q["sql"] for q in queries.captured_queries if '"portal_sitesections"' in q["sql"]]
    return sum(not sql.startswith("SELECT 1 AS") for sql in reads)


@pytest.mark.parametrize("url", ["/", "/pibg/", "/search/?q=sports", "/events/"])
def test_site_sections_are_read_once_per_page(client, content, url):
    pause("documents")
    assert site_sections_reads(client, url) == 1


@pytest.mark.django_db
def test_admin_event_list_reads_site_sections_once(admin_client, make_event):
    for days in (1, 2, 3):
        make_event(days=days)
    pause("events")
    assert site_sections_reads(admin_client, reverse("admin:portal_event_changelist")) == 1


@pytest.mark.django_db
def test_outside_a_request_each_check_reads_fresh():
    from portal.sections import is_on

    assert is_on("news")
    pause("news")
    assert not is_on("news")


@pytest.mark.django_db
def test_pibg_page_hides_events_and_documents_that_are_paused(client, content):
    Event.objects.create(
        title="PIBG AGM", kind=Event.PIBG, starts_at=timezone.now() + timedelta(days=5)
    )
    Document.objects.create(
        title="PIBG minutes", group=Document.PIBG, file=SimpleUploadedFile("m.pdf", b"%PDF-1.4")
    )
    pause("events", "documents")
    html = client.get("/pibg/").content.decode()
    assert "PIBG AGM" not in html
    assert "All PIBG events" not in html
    assert "PIBG minutes" not in html


@pytest.mark.django_db
def test_event_and_album_pages_drop_links_to_paused_sections(client, content):
    event = Event.objects.get(title="Sports day")
    album = Album.objects.get()
    pause("photos")
    assert album.get_absolute_url() not in client.get(event.get_absolute_url()).content.decode()
    record = SiteSections.load()
    record.photos, record.events = True, False
    record.save()
    assert event.get_absolute_url() not in client.get(album.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_unsubscribe_page_offers_sign_up_only_while_events_are_on(client):
    subscriber = Subscriber.objects.create(email="parent@example.com", is_active=False)
    url = subscriber.get_unsubscribe_url()
    assert "Sign up again on the home page" in client.get(url).content.decode()
    pause("events")
    assert "Sign up again on the home page" not in client.get(url).content.decode()


@pytest.mark.parametrize("key", ["events", "news", "documents", "achievements", "photos"])
def test_search_leaves_out_paused_sections(content, key):
    assert key in [s.key for s in find("sports day")]
    pause(key)
    keys = [s.key for s in find("sports day")]
    assert key not in keys
    assert len(keys) == 4


@pytest.mark.django_db
def test_no_event_emails_while_events_are_paused(make_event, mailoutbox):
    Subscriber.objects.create(email="parent@example.com")
    event = make_event(days=1)
    pause("events")
    assert notify_subscribers(event) == 0
    assert send_reminders([event]) == 0
    assert mailoutbox == []
    event.refresh_from_db()
    assert event.notified_at is None
    assert event.reminded_at is None


@pytest.mark.django_db
def test_email_action_works_again_once_events_are_back_on(admin_client, make_event, mailoutbox):
    Subscriber.objects.create(email="parent@example.com")
    event = make_event()
    pause("events")
    url = reverse("admin:portal_event_changelist")
    data = {"action": "email_subscribers", "_selected_action": [event.pk]}
    response = admin_client.post(url, data, follow=True)
    assert "Events is paused, so no emails were sent." in response.content.decode()
    assert mailoutbox == []

    record = SiteSections.load()
    record.events = True
    record.save()
    admin_client.post(url, data)
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_posts_in_paused_sections_cannot_be_shared(admin_client, make_event):
    event = make_event()
    assert is_public(event)
    pause("events")
    assert not is_public(event)
    html = admin_client.get(reverse("admin:portal_event_change", args=[event.pk])).content.decode()
    assert "Share on WhatsApp" not in html
    assert "Not shown to parents right now, so it can&#x27;t be shared." in html
