# Pausing Site Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Superusers can pause News, Events, Photos, Documents, PIBG, Achievements or Search from one admin page, and a paused section disappears from the whole public site until it is switched back on.

**Architecture:** One `SiteSections` record (pk 1, like `SchoolContact`) holds seven booleans. `portal/sections.py` exposes `is_on(key)` and a `@section(key)` view decorator that renders a 503 "paused" page. The context processor adds the record as `site_sections` for menu, footer and cross-section links; `home`, `pibg`, `event_detail`, `search.find`, the email senders and the WhatsApp share check consult it too.

**Tech Stack:** Django 6.1, django-modeltranslation (admin base class only; the new model is not translated), pytest-django, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-11-site-sections-design.md`

## Global Constraints

- Keys, exactly: `news`, `events`, `photos`, `documents`, `pibg`, `achievements`, `search`. All `default=True`.
- Paused pages answer HTTP 503 with `portal/section_paused.html`, which has `<meta name="robots" content="noindex">`.
- Paused page copy: heading "This section is not available right now", line "Please check back later.", links "Go to the home page" and "Contact the school".
- Only superusers can see or change Site sections; `setup_roles` gives Editors nothing on `sitesections`.
- While Events is paused, `notify_subscribers` and `send_reminders` send nothing, return 0, and do not mark events as notified/reminded. Nothing is queued.
- Admin warning text, exactly: "Events is paused, so no emails were sent."
- Always on: home, contact, urgent notices, unsubscribe, admin, manifest.
- Every user-facing string translated: `scripts/translations.py update`, fill Tamil and Malay, `compile`. Never leave an entry empty.
- Run `pytest` and `ruff check .` before calling a task done. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never stage `media.zip`.
- Ruling (plan vs spec): the spec names the context variable `sections`, but `search.html` already receives a `sections` list from its view, which would shadow it in `base.html` and hide the whole menu on the search page. The context variable is `site_sections`.
- Ruling (plan vs spec): "links into a paused section are hidden" also covers lists that link into it: the PIBG page drops its meetings when Events is paused and its documents when Documents is paused; an event page drops its album links when Photos is paused.

## Review Focus

- Everything paused at once: the home page still renders (welcome band only), with no empty bands and no section links. Test in Task 3.
- An editor who was given `change_sitesections` by hand still cannot open Site sections. Test in Task 1.
- A paused detail URL with an id that doesn't exist answers 503, not 404 (the decorator runs first), so old links never leak which ids exist. Test in Task 2.
- Switching a section off and back on restores its pages. Test in Task 2.
- An event published while Events is paused is not marked notified, so "Email subscribers" works once Events is back on. Test in Task 4.

---

### Task 1: SiteSections record and superuser-only admin

**Files:**
- Modify: `portal/models.py` (add `SiteSections` after `CommitteeMember`)
- Create: `portal/migrations/0016_sitesections.py` (generated)
- Modify: `portal/admin.py` (import `SiteSections`; add `SiteSectionsAdmin` after `PibgAdmin`)
- Test: `tests/test_sections.py` (new)

**Interfaces:**
- Produces: `SiteSections` model with BooleanFields `news, events, photos, documents, pibg, achievements, search`; `SiteSections.load() -> SiteSections` (unsaved all-on record when none exists); `save()` pins pk=1.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sections.py`:

```python
import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.urls import reverse

from portal.models import SiteSections

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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py -q`
Expected: collection error, `ImportError: cannot import name 'SiteSections'`.

- [ ] **Step 3: Add the model**

In `portal/models.py`, after the `CommitteeMember` class:

```python
class SiteSections(models.Model):
    """Which parts of the public site are switched on. There is only ever one of these."""

    news = models.BooleanField(default=True, help_text="The News pages.")
    events = models.BooleanField(
        default=True,
        help_text="The Events pages and calendar files. "
        "Also stops email sign-ups, event emails and reminders.",
    )
    photos = models.BooleanField(
        default=True, help_text="The photo albums, and album photos on the home page."
    )
    documents = models.BooleanField(default=True, help_text="The Documents page and its links.")
    pibg = models.BooleanField("PIBG", default=True, help_text="The PIBG page.")
    achievements = models.BooleanField(
        default=True, help_text="The Achievements pages and their photos."
    )
    search = models.BooleanField(default=True, help_text="The Search page.")

    class Meta:
        verbose_name = verbose_name_plural = "site sections"

    def __str__(self) -> str:
        return "Site sections"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1  # one record, however it is saved
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSections":
        return cls.objects.first() or cls()
```

Run: `.venv/Scripts/python manage.py makemigrations portal -n sitesections`
Expected: `portal/migrations/0016_sitesections.py` with `Create model SiteSections`.

- [ ] **Step 4: Add the admin**

In `portal/admin.py`, add `SiteSections` to the `from .models import (...)` list, and after `PibgAdmin`:

```python
@admin.register(SiteSections)
class SiteSectionsAdmin(SingleRecordAdmin):
    """Untick a section to pause it on the public site. Superusers only."""

    fieldsets = [
        (
            None,
            {
                "description": "Untick a section to hide it from parents for a while. "
                "Nothing is deleted, and staff can keep preparing posts.",
                "fields": ["news", "events", "photos", "documents", "pibg", "achievements", "search"],
            },
        )
    ]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)
```

`setup_roles.py` needs no change: Editors get no `sitesections` permission because it is not listed.

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py -q`
Expected: 8 passed.

Run: `.venv/Scripts/python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 6: Commit**

```bash
git add portal/models.py portal/migrations/0016_sitesections.py portal/admin.py tests/test_sections.py
git commit -m "Add the Site sections record, editable by superusers only

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Paused page and the section decorator on every section view

**Files:**
- Create: `portal/sections.py`
- Create: `portal/templates/portal/section_paused.html`
- Modify: `portal/views.py` (decorate views)
- Modify: `locale/ta/LC_MESSAGES/django.po`, `locale/ms/LC_MESSAGES/django.po` (+ compiled `.mo`)
- Test: `tests/test_sections.py`

**Interfaces:**
- Consumes: `SiteSections.load()` (Task 1).
- Produces: `portal.sections.KEYS: tuple[str, ...]`; `is_on(key: str) -> bool`; `section(key: str)` decorator. `section()` raises `ValueError` for an unknown key at import time.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sections.py` (add imports at the top: `from datetime import timedelta`, `from django.core.files.uploadedfile import SimpleUploadedFile`, `from django.utils import timezone`, and extend the models import to `from portal.models import Achievement, Album, Announcement, Document, Event, SiteSections, Subscriber`):

```python
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
        title="Sports day gold", category=Achievement.CATEGORIES[0][0],
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py -q`
Expected: the new paused tests FAIL (pages answer 200/404, not 503); `test_unknown_section_key_is_a_mistake` fails with `ModuleNotFoundError: No module named 'portal.sections'`.

- [ ] **Step 3: Add `portal/sections.py`**

```python
"""Sections of the public site that a superuser can pause (Admin → Site sections)."""

from functools import wraps

from django.shortcuts import render

from .models import SiteSections

KEYS = ("news", "events", "photos", "documents", "pibg", "achievements", "search")


def is_on(key: str) -> bool:
    return getattr(SiteSections.load(), key)


def section(key: str):
    """While the section is paused, the view answers with the paused page (503: temporary)."""
    if key not in KEYS:
        raise ValueError(f"Unknown site section: {key}")

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_on(key):
                return render(request, "portal/section_paused.html", status=503)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
```

- [ ] **Step 4: Add the paused page**

Create `portal/templates/portal/section_paused.html`:

```django
{% extends "portal/base.html" %}
{% load i18n %}

{% block title %}{% translate "This section is not available right now" %}, {{ school_name }}{% endblock %}
{% block head %}<meta name="robots" content="noindex">{% endblock %}

{% block content %}
<header class="page-head">
  <h1>{% translate "This section is not available right now" %}</h1>
  <p class="meta">{% translate "Please check back later." %}</p>
</header>
<p><a href="{% url 'portal:home' %}">{% translate "Go to the home page" %}</a></p>
<p><a href="{% url 'portal:contact' %}">{% translate "Contact the school" %}</a></p>
{% endblock %}
```

- [ ] **Step 5: Decorate the views**

In `portal/views.py` add `from .sections import section`, then put the decorator directly above each of these `def`s (below `@require_POST` on `subscribe`):

| Decorator | Views |
|---|---|
| `@section("news")` | `announcement_list`, `announcement_detail` |
| `@section("events")` | `event_list`, `event_detail`, `event_calendar`, `calendar_feed`, `subscribe` |
| `@section("photos")` | `album_list`, `album_detail` |
| `@section("documents")` | `document_list`, `document_open` |
| `@section("pibg")` | `pibg` |
| `@section("achievements")` | `achievement_list`, `achievement_detail`, `private_media` |
| `@section("search")` | `search` |

For example:

```python
@require_POST
@section("events")
def subscribe(request):
```

- [ ] **Step 6: Translate the new words**

Run: `.venv/Scripts/python scripts/translations.py update`
Fill the three new entries in both files:

| msgid | Tamil (`locale/ta/...`) | Malay (`locale/ms/...`) |
|---|---|---|
| This section is not available right now | இந்தப் பகுதி இப்போது கிடைக்கவில்லை | Bahagian ini tidak tersedia buat masa ini |
| Please check back later. | பிறகு மீண்டும் பாருங்கள். | Sila semak semula kemudian. |
| Go to the home page | முகப்புப் பக்கத்திற்குச் செல்லுங்கள் | Pergi ke laman utama |

Run: `.venv/Scripts/python scripts/translations.py compile`

- [ ] **Step 7: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py tests/test_languages.py -q`
Expected: all pass (including `test_every_phrase_has_a_translation`).

- [ ] **Step 8: Commit**

```bash
git add portal/sections.py portal/templates/portal/section_paused.html portal/views.py locale tests/test_sections.py
git commit -m "Show a paused page for switched-off sections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Hide paused sections from the menu, footer, home page, links and search

**Files:**
- Modify: `portal/context_processors.py`
- Modify: `portal/templates/portal/base.html`, `home.html`, `pibg.html`, `album_detail.html`, `unsubscribe.html`
- Modify: `portal/views.py` (`home`, `pibg`, `event_detail`)
- Modify: `portal/search.py` (`find`)
- Test: `tests/test_sections.py`

**Interfaces:**
- Consumes: `SiteSections.load()`, `pause()` test helper, `content` fixture (Tasks 1–2).
- Produces: template context variable `site_sections` (a lazy `SiteSections`) on every page rendered with a request.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sections.py` (add `import io`, `from PIL import Image`, `Photo` to the models import, and `from portal.search import find`):

```python
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
    album = Album.objects.get()
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(buffer, "JPEG")  # Photo.save() shrinks it
    Photo.objects.create(album=album, image=SimpleUploadedFile("a.jpg", buffer.getvalue()))
    assert "See the photos" in client.get("/").content.decode()
    pause("photos")
    html = client.get("/").content.decode()
    assert "See the photos" not in html
    assert "/gallery/" not in html


@pytest.mark.django_db
def test_home_with_everything_paused_is_just_the_welcome(client, content):
    pause(*KEYS)
    response = client.get("/")
    html = response.content.decode()
    assert response.status_code == 200
    assert "Welcome to" in html
    for path in MENU.values():
        assert f'href="{path}' not in html


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
```

`unsubscribe.html` shows "Sign up again on the home page" on a GET for an already inactive subscriber, so the plain GETs above exercise it.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py -q`
Expected: the new menu, home, PIBG, event/album, unsubscribe and search tests FAIL (links still present); `test_menu_is_complete_on_the_search_page` passes already (it guards the `site_sections` naming).

- [ ] **Step 3: Add `site_sections` to every page**

`portal/context_processors.py`:

```python
from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .models import SiteSections, SocialLink, UrgentNotice


def school(request):
    return {
        ...existing keys unchanged...,
        # Not "sections": the search page already uses that name for its results.
        "site_sections": SimpleLazyObject(SiteSections.load),
    }
```

- [ ] **Step 4: Menu and footer**

In `base.html`, wrap each switchable link in both the `site-nav` and `footer-links` navs, e.g.:

```django
{% if site_sections.news %}<a href="{% url 'portal:announcement_list' %}"{% if "announcement" in current %} aria-current="page"{% endif %}>{% translate "News" %}</a>{% endif %}
```

and the same with `site_sections.events`, `.photos`, `.documents`, `.pibg`, `.achievements`, `.search` around the Events, Photos, Documents, PIBG, Achievements and Search links. Contact and Staff sign in stay unwrapped.

- [ ] **Step 5: Home page**

In `views.home`, read the record once and skip paused parts:

```python
def home(request):
    on = SiteSections.load()
    # News leads the page: the pinned update (or the latest one) fills the big top section.
    # With no news at all, the next event takes its place.
    news = list(Announcement.objects.published()[:4]) if on.news else []
    lead_news = news[0] if news else None
    upcoming = list(Event.objects.published().upcoming()[:5]) if on.events else []
    hero_event = upcoming[0] if upcoming and lead_news is None else None
    coming_up = [e for e in upcoming if e != hero_event][:4]

    featured_album = None
    if on.photos:
        albums_with_photos = Album.objects.filter(is_published=True, photos__isnull=False).distinct()
        featured_album = albums_with_photos.prefetch_related("photos").first()
    album_photos = list(featured_album.photos.all()) if featured_album else []
    ...rest unchanged...
```

Add `SiteSections` to the views' models import. In `home.html`:
- wrap the whole `<section class="split wrap" aria-labelledby="news-title">…</section>` in `{% if site_sections.news %}…{% endif %}`;
- wrap the `events-title` split section and the `band--signup` section each in `{% if site_sections.events %}…{% endif %}`;
- in the welcome branch, wrap `<p><a class="button button--torch" href="#subscribe-title">…Get event emails…</a></p>` in `{% if site_sections.events %}…{% endif %}`.

- [ ] **Step 6: PIBG, event and album pages, unsubscribe**

`views.pibg`: build `upcoming`/`past` only when Events is on and `documents` only when Documents is on:

```python
def pibg(request):
    on = SiteSections.load()
    info = Pibg.load()
    meetings = Event.objects.published().filter(kind=Event.PIBG) if on.events else Event.objects.none()
    documents = Document.objects.published().filter(group=Document.PIBG) if on.documents else []
    context = {
        "pibg": info,
        "committee": info.members(),
        "upcoming": list(meetings.upcoming().order_by("starts_at")),
        "past": list(meetings.past().order_by("-starts_at")[:PAST_MEETINGS]),
        "documents": list(documents),
    }
    ...rest unchanged...
```

`pibg.html`: wrap the "All PIBG events" paragraph in `{% if site_sections.events %}…{% endif %}`.

`views.event_detail`: `albums = event.albums.filter(is_published=True) if is_on("photos") else []` (import `is_on` from `.sections`).

`album_detail.html` line 9: `{% if album.event and site_sections.events %}`.

`unsubscribe.html`: wrap only the `<a …>Sign up again on the home page</a>` link in `{% if site_sections.events %}…{% endif %}`; the "already doesn't get event emails" sentence stays.

- [ ] **Step 7: Search**

In `portal/search.py` import `SiteSections` from `.models` and skip paused sections in `find()`:

```python
    on = SiteSections.load()
    sections = []
    for key, heading, queryset, fields in searches:
        if not getattr(on, key):
            continue
        found = queryset.filter(matching(fields, terms))
```

- [ ] **Step 8: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py tests/test_search.py tests/test_pibg.py tests/test_content.py tests/test_subscriptions.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add portal/context_processors.py portal/templates portal/views.py portal/search.py tests/test_sections.py
git commit -m "Hide paused sections from the menu, home page, links and search

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: No event emails while Events is paused; admin warnings; WhatsApp share

**Files:**
- Modify: `portal/notifications.py`
- Modify: `portal/admin.py` (`EventAdmin.email_subscribers`, import review, `WhatsAppShareMixin`)
- Modify: `portal/whatsapp.py`
- Test: `tests/test_sections.py`, `tests/test_import.py`

**Interfaces:**
- Consumes: `is_on(key)` (Task 2), `pause()` helper (Task 1).
- Produces: `portal.whatsapp.section_paused(obj) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sections.py` (imports: `from portal.notifications import notify_subscribers, send_reminders`, `from portal.whatsapp import is_public`):

```python
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
    assert "Not shown to parents right now, so it can't be shared." in html
```

Append to `tests/test_import.py` (add `from portal.models import SiteSections` to its imports):

```python
def test_publish_with_email_while_events_are_paused_warns(admin_client, mailoutbox):
    Subscriber.objects.create(email="parent@example.com")
    SiteSections(events=False).save()
    upload_sample(admin_client)
    batch = EventImport.objects.get()
    fair = batch.events.get(title="Science fair")

    data = review_post(batch, "publish", selected=[fair])
    data["email_parents"] = "1"
    url = reverse("admin:portal_event_import_review", args=[batch.pk])
    response = admin_client.post(url, data, follow=True)

    fair.refresh_from_db()
    assert fair.is_published
    assert mailoutbox == []
    assert "Events is paused, so no emails were sent." in response.content.decode()
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py tests/test_import.py -q`
Expected: the four new tests FAIL (emails sent, no warning, share button shown).

- [ ] **Step 3: Stop the emails**

`portal/notifications.py`: `from .sections import is_on`, then as the first lines of `notify_subscribers`:

```python
    if not is_on("events"):
        return 0  # parents can't open event pages while Events is paused
```

and in `send_reminders`, before `events = reminder_events() ...`:

```python
    if not is_on("events"):
        return 0
```

- [ ] **Step 4: Admin warnings**

`portal/admin.py`: `from .sections import is_on`. Add a module constant next to the other admin helpers:

```python
EVENTS_PAUSED = "Events is paused, so no emails were sent."
```

At the top of `EventAdmin.email_subscribers`:

```python
        if not is_on("events"):
            self.message_user(request, EVENTS_PAUSED, messages.WARNING)
            return
```

In the import review publish branch, replace the `if request.POST.get("email_parents"):` block with:

```python
                        if request.POST.get("email_parents"):
                            if is_on("events"):
                                sent = sum(notify_subscribers(event) for event in to_publish)
                                note += f" Sent {sent} email(s) to parents."
                            else:
                                note += f" {EVENTS_PAUSED}"
```

- [ ] **Step 5: WhatsApp share**

`portal/whatsapp.py`: `from .sections import is_on`, and:

```python
SECTIONS = {
    Event: "events",
    Announcement: "news",
    Document: "documents",
    Achievement: "achievements",
}


def section_paused(obj) -> bool:
    """The post's section is switched off in Site sections, so its link opens the paused page."""
    key = SECTIONS.get(type(obj))
    return key is not None and not is_on(key)
```

At the top of `is_public`: `if section_paused(obj): return False`.

In `WhatsAppShareMixin.whatsapp_share` (admin.py), check it before the "remove after" branch so a paused document doesn't get the wrong reason:

```python
        if not is_public(obj):
            if section_paused(obj):
                return "Not shown to parents right now, so it can't be shared."
            if obj.is_published and getattr(obj, "remove_after", None):
```

and import it: `from .whatsapp import is_public, section_paused, share_url`.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_sections.py tests/test_import.py tests/test_whatsapp.py tests/test_reminders.py tests/test_subscriptions.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add portal/notifications.py portal/admin.py portal/whatsapp.py tests/test_sections.py tests/test_import.py
git commit -m "Send no event emails and share nothing from paused sections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Browser check, docs, full suite

**Files:**
- Modify: `tests/test_browser.py`
- Modify: `CLAUDE.md` (Layout)

**Interfaces:**
- Consumes: `SiteSections` (Task 1), the paused page (Task 2).

- [ ] **Step 1: Write the browser test**

Add `SiteSections` to the `portal.models` import in `tests/test_browser.py`, and append:

```python
@pytest.mark.parametrize("language", ["ta", "ms"])
def test_paused_page_fits_a_phone(page, live_server, site, language):
    SiteSections(news=False).save()
    use_language(page, live_server, language)
    page.set_viewport_size(PHONE)

    response = page.goto(live_server.url + "/news/")

    assert response.status == 503
    assert page.locator("h1").count() == 1
    assert page.locator('.site-nav a[href="/news/"]').count() == 0
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"paused page scrolls sideways by {overflow}px"
```

(No `collect_errors` here: Chrome logs a console error for any 503 document.)

- [ ] **Step 2: Run it**

Run: `.venv/Scripts/python -m pytest tests/test_browser.py -k paused -q`
Expected: 2 passed. If Tamil overflows, the heading's long word is the cause (as with search): shorten the Tamil translation, e.g. "இப்பகுதி தற்போது இல்லை", recompile, and ledger the ruling.

- [ ] **Step 3: Document it**

In `CLAUDE.md` under Layout, after the PIBG bullet:

```markdown
- `portal/sections.py` pausing sections (Admin → Site sections, superusers only): one
  `SiteSections` record; `@section(key)` on views answers 503 with `section_paused.html`, and
  templates check `site_sections.<key>` (not `sections`, which the search page uses). Paused
  Events also stops sign-ups and event emails. New public views in a section need the decorator
```

- [ ] **Step 4: Full suite and lint**

Run: `.venv/Scripts/python -m pytest -q` (redirect to a file, read the tail)
Expected: all pass (≈344 existing + the new ones).
Run: `.venv/Scripts/ruff check .` and `.venv/Scripts/ruff format --check .`
Expected: clean.
Run: `.venv/Scripts/python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_browser.py CLAUDE.md
git commit -m "Check the paused page on a phone and document site sections

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
