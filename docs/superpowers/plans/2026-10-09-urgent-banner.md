# Urgent Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff can put an urgent one-line notice at the top of every page for a set time, and share it on WhatsApp.

**Architecture:** An `UrgentNotice` model with a `showing()` queryset, fed to every page by the existing `school` context processor and rendered as a bar in `base.html`. The admin reuses `AnyLanguageAdmin` and `WhatsAppShareMixin`; `portal/whatsapp.py` gains a template for notices.

**Tech Stack:** Django 6.1, django-modeltranslation, pytest-django, Playwright, `scripts/translations.py`.

**Spec:** `docs/superpowers/specs/2026-10-09-urgent-banner-design.md`

## Global Constraints

- Message: max 200 characters, translated (`message_ta/ms/en`), at least one language ("Write the notice in at least one language.").
- Link: optional, `http`/`https` only.
- Show until must be after Show from: "The notice must end after it starts."
- Default Show until: 23:59:59 today in `TIME_ZONE`.
- Showing = published and `starts_at <= now < ends_at`, newest `starts_at` first.
- Bar: navy background, white text, torch-yellow "Urgent" label; no close button; no red.
- WhatsApp text: `*Urgent:* <message>` (label translated, site default language), blank line, then the link or `SITE_URL/`.
- Every new phrase translated into Tamil and Malay; `scripts/translations.py update/compile`.
- Tests: `.venv\Scripts\python -m pytest`, `ruff check .`, `ruff format --check .`.

## Review Focus

1. A notice whose end has just passed disappears on the next page load (no caching). Test in Task 1 (`showing()` at a given moment).
2. A long Tamil notice with a Details link must not make a 360 px phone scroll sideways. Browser test in Task 2.
3. A notice published in Malay only still shows to a Tamil visitor (fallback). Test in Task 2.
4. A `javascript:` link is refused. Test in Task 1.
5. Editors without superuser rights can add a notice. Test in Task 3.

---

### Task 1: The notice record

**Files:** Modify `portal/models.py`, `portal/translation.py`; generate `portal/migrations/0013_urgentnotice.py`; create `tests/test_urgent.py`.

**Interfaces — Produces:** `UrgentNotice` (`message`, `link`, `starts_at`, `ends_at`, `is_published`), `UrgentNotice.objects.showing(now=None)`, `end_of_today()`, `UrgentNotice.get_absolute_url() -> "/"`, property `share_link -> str` (the link, else `SITE_URL + "/"`).

- [ ] **Step 1: Failing tests** — create `tests/test_urgent.py`:

```python
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
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
    assert not UrgentNotice.objects.showing(now=current.ends_at).exists()


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
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_urgent.py -q`. Expected: `ImportError: cannot import name 'UrgentNotice'`.

- [ ] **Step 3: Implement** — append to `portal/models.py`:

```python
def end_of_today():
    """23:59:59 today, school time: the default end of an urgent notice."""
    return timezone.make_aware(datetime.combine(timezone.localdate(), time(23, 59, 59)))


class UrgentNoticeQuerySet(models.QuerySet):
    def showing(self, now=None):
        now = now or timezone.now()
        return self.filter(is_published=True, starts_at__lte=now, ends_at__gt=now).order_by(
            "-starts_at"
        )


class UrgentNotice(models.Model):
    """One line at the top of every page for a set time, e.g. "School closed today"."""

    message = models.CharField(
        max_length=200, help_text="One line, e.g. “School is closed today because of flooding.”"
    )
    link = models.URLField(
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Optional. A page with more details, e.g. a news post or a document.",
    )
    starts_at = models.DateTimeField("show from", default=timezone.now)
    ends_at = models.DateTimeField(
        "show until", default=end_of_today, help_text="It disappears by itself after this."
    )
    is_published = models.BooleanField("published", default=True)

    objects = UrgentNoticeQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at"]
        verbose_name = "urgent notice"

    def __str__(self) -> str:
        return self.message

    def get_absolute_url(self) -> str:
        return reverse("portal:home")

    @property
    def share_link(self) -> str:
        return self.link or settings.SITE_URL + reverse("portal:home")

    def clean(self) -> None:
        require_one_language(self, "message", "Write the notice in at least one language.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The notice must end after it starts."})
```

`portal/translation.py`: import `UrgentNotice`, register `fields = ("message",)` with `AnyLanguage`. Then `.venv\Scripts\python manage.py makemigrations portal -n urgentnotice`.

- [ ] **Step 4: Run** the tests. Expected: pass.
- [ ] **Step 5: Commit** "Add urgent notices".

---

### Task 2: The bar on every page

**Files:** Modify `portal/context_processors.py`, `portal/templates/portal/base.html`, `portal/static/portal/style.css`, `tests/test_browser.py`, `tests/test_urgent.py`; translations.

**Interfaces — Consumes:** `UrgentNotice.objects.showing()`. **Produces:** context variable `urgent_notices`.

- [ ] **Step 1: Failing tests** — append to `tests/test_urgent.py` (add `from django.urls import reverse`):

```python
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
```

In `tests/test_browser.py`'s `site` fixture add a long Tamil notice:

```python
    UrgentNotice.objects.create(
        message_ta="வெள்ளம் காரணமாக இன்று பள்ளி மூடப்பட்டுள்ளது. திங்கள்கிழமை வகுப்புகள் வழக்கம்போல் நடைபெறும்.",
        link="https://example.com/news/1/",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
```

(import `UrgentNotice` there).

- [ ] **Step 2: Run** — Expected: the three new tests fail (no `urgent-label` in the page).

- [ ] **Step 3: Implement**
  - `portal/context_processors.py`: import `UrgentNotice`; add `"urgent_notices": UrgentNotice.objects.showing(),`.
  - `base.html`, directly after the skip link:

    ```html
      {% if urgent_notices %}
        <div class="urgent" role="region" aria-label="{% translate 'Urgent notices' %}">
          {% for notice in urgent_notices %}
            <p class="urgent-notice wrap"><strong class="urgent-label">{% translate "Urgent" %}</strong> {{ notice.message }}{% if notice.link %} <a href="{{ notice.link }}">{% translate "Details" %}</a>{% endif %}</p>
          {% endfor %}
        </div>
      {% endif %}
    ```

  - `style.css`, after the `.site-header` rules:

    ```css
    /* Urgent notices: one line above the header on every page */

    .urgent { background: var(--navy); color: var(--white); }
    .urgent-notice { margin: 0; padding-block: 0.7rem; overflow-wrap: anywhere; }
    .urgent-notice + .urgent-notice { border-top: 1px solid rgb(255 255 255 / 0.2); }
    .urgent-label {
      display: inline-block;
      margin-right: 0.5rem;
      padding: 0.05rem 0.5rem;
      border-radius: var(--radius);
      background: var(--torch);
      color: var(--navy);
    }
    .urgent a { color: var(--white); font-weight: 600; }
    ```

  - Translations:

    | English | Tamil | Malay |
    |---|---|---|
    | Urgent | அவசரம் | Penting |
    | Urgent notices | அவசர அறிவிப்புகள் | Makluman penting |
    | Details | விவரங்கள் | Butiran |

- [ ] **Step 4: Run** the full suite (browser tests included). Expected: all pass.
- [ ] **Step 5: Commit** "Show urgent notices at the top of every page".

---

### Task 3: Admin, WhatsApp, Editors

**Files:** Modify `portal/admin.py`, `portal/whatsapp.py`, `portal/management/commands/setup_roles.py`, `tests/test_urgent.py`; create `portal/templates/portal/whatsapp/urgent.txt`.

**Interfaces — Consumes:** `UrgentNotice`, `share_link`, `showing()`; existing `WhatsAppShareMixin`, `AnyLanguageAdmin`, `share_message`, `is_public`.

- [ ] **Step 1: Failing tests** — append (imports: `Group`, `User`, `call_command`, `share_message`):

```python
def test_whatsapp_message(notice, settings):
    settings.SITE_URL = "https://school.example"
    with_link = notice("Sekolah ditutup.", link="https://school.example/news/4/")
    without = notice("Kelas dalam talian esok.")

    # Shared messages use the site's default language, Tamil.
    assert share_message(with_link) == (
        "*அவசரம்:* Sekolah ditutup.\n\nhttps://school.example/news/4/"
    )
    assert share_message(without).endswith("\n\nhttps://school.example/")


def test_admin_list_shares_only_showing_notices(notice, admin_client):
    notice("Now")
    notice("Over", starts_at=timezone.now() - timedelta(hours=2), ends_at=timezone.now())

    html = admin_client.get(reverse("admin:portal_urgentnotice_changelist")).content.decode()

    assert html.count("Share on WhatsApp") == 1


@pytest.mark.django_db
def test_editor_can_add_a_notice(client):
    call_command("setup_roles", stdout=None)
    editor = User.objects.create_user("editor", password="x", is_staff=True)
    editor.groups.add(Group.objects.get(name="Editors"))
    client.force_login(editor)

    response = client.post(
        reverse("admin:portal_urgentnotice_add"),
        {
            "message_ms": "Sekolah ditutup hari ini.",
            "starts_at_0": timezone.localdate().isoformat(),
            "starts_at_1": "00:00",
            "ends_at_0": timezone.localdate().isoformat(),
            "ends_at_1": "23:59",
            "is_published": "on",
        },
    )

    assert response.status_code == 302, response.content.decode()[-2000:]
    assert UrgentNotice.objects.get().message == "Sekolah ditutup hari ini."
```

- [ ] **Step 2: Run** — Expected: `KeyError: <class 'portal.models.UrgentNotice'>`, `NoReverseMatch`, permission failure.

- [ ] **Step 3: Implement**
  - `portal/templates/portal/whatsapp/urgent.txt`:

    ```
    {% load i18n %}{% autoescape off %}*{% translate "Urgent" %}:* {{ post.message }}

    {{ post.share_link }}
    {% endautoescape %}
    ```

  - `portal/whatsapp.py`: import `UrgentNotice`; `TEMPLATES[UrgentNotice] = "portal/whatsapp/urgent.txt"`; widen type hints; at the top of `is_public`: `if isinstance(obj, UrgentNotice): return UrgentNotice.objects.showing().filter(pk=obj.pk).exists()`.
  - `portal/admin.py`: import `UrgentNotice`; add

    ```python
    @admin.register(UrgentNotice)
    class UrgentNoticeAdmin(WhatsAppShareMixin, AnyLanguageAdmin):
        list_display = ["message", "starts_at", "ends_at", "is_published", "showing_now", "whatsapp_share"]
        list_filter = ["is_published"]
        search_fields = in_all_languages("message")
        readonly_fields = ["whatsapp_share"]

        @admin.display(description="showing now", boolean=True)
        def showing_now(self, obj):
            return UrgentNotice.objects.showing().filter(pk=obj.pk).exists()
    ```

  - `setup_roles.py`: `"urgentnotice": ["add", "change", "delete", "view"],`.

- [ ] **Step 4: Run** the full suite and both ruff checks. Expected: all pass.
- [ ] **Step 5: Commit** "Manage and share urgent notices in the admin".

---

### Task 4: Check it in the browser

- [ ] With a long Tamil notice and a Details link in the local database, look at the home page and an event page at 360 px and 1280 px in Tamil and English; delete the sample. Commit any CSS fix.
