# Achievements Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public Achievements page (one year at a time, category filters, detail pages) built from staff-entered achievements with pupils and photos, applying consent and short-name privacy rules.

**Architecture:** `Achievement` with inline `AchievementPupil` and `AchievementPhoto` models in `portal/models.py`; name rules are small pure functions next to them. Views follow `event_list` (query-string year and type, `urlencode`). Admin reuses `AnyLanguageAdmin`, `WhatsAppShareMixin` and the photo shrinking in `portal/images.py`.

**Tech Stack:** Django 6.1, django-modeltranslation, Pillow, pytest-django, Playwright, `scripts/translations.py`.

**Spec:** `docs/superpowers/specs/2026-10-09-achievements-design.md`

## Global Constraints

- Categories (key → label, filter order): `academic` Academic, `sports` Sports, `arts` Arts and culture, `tamil` Tamil language, `other` Other.
- Levels: `school` School, `district` District, `state` State, `national` National, `international` International; State and above are "high".
- Patronymic markers (case-insensitive): a/l, a/p, s/o, d/o, bin, binti, bt, bte.
- No consent → "a Year N pupil" (N = first digit in the class) or "a pupil".
- Photos shown only if every pupil has consent (no pupils → shown).
- Achievement pages: `<meta name="robots" content="noindex">`.
- Query: `?year=YYYY&type=<category>`; bad values → latest year / All.
- Every new phrase translated into Tamil and Malay; `scripts/translations.py update/compile`.
- Tests: `.venv\Scripts\python -m pytest`, `ruff check .`, `ruff format --check .`; tests that save photos set `MEDIA_ROOT` to `tmp_path`.

## Review Focus

1. A pupil with consent whose class is empty shows just the short name, no empty brackets. Test in Task 1.
2. Names with extra spaces or lower-case markers ("Kavin  A/L raju") shorten correctly. Test in Task 1.
3. Unticking consent for one pupil hides that achievement's photos on both list and detail pages. Test in Task 2.
4. Switching the filter to a category with no wins in the current year falls back to that category's latest year. Test in Task 2.
5. The WhatsApp message never contains a full name unless "show full name" is ticked. Test in Task 3.

---

### Task 1: Records and privacy rules

**Files:** Modify `portal/models.py`, `portal/translation.py`; generate migration `0014_achievement`; create `tests/test_achievements.py`.

**Interfaces — Produces:** `short_name(full: str) -> str`; `Achievement` (`title`, `description`, `date`, `category`, `level`, `is_published`, constants above, `CATEGORIES`, `LEVELS`, `HIGH_LEVELS`), `Achievement.objects.published()`, properties `photos_allowed`, `is_high_level`, `pupil_line` (displayed names joined by ", "), `consent_summary`; `AchievementPupil` (`achievement` FK `pupils`, `name`, `class_name`, `consent`, `show_full_name`, property `display`); `AchievementPhoto` (`achievement` FK `photos`, `image`, `caption`, `order`).

- [ ] **Step 1: Failing tests** — create `tests/test_achievements.py`:

```python
from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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
        assert AchievementPupil(name="Kavin a/l Raju", class_name="5 Mutiara", consent=True).display == (
            "Kavin R. (5 Mutiara)"
        )
        assert AchievementPupil(name="Kavin a/l Raju", class_name="", consent=True).display == "Kavin R."
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
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_achievements.py -q`. Expected: `ImportError: cannot import name 'Achievement'`.

- [ ] **Step 3: Implement** — in `portal/models.py` (it already imports `re`, `date`, `_`, `shrink_new_upload`, `require_one_language`), append:

```python
PATRONYMIC_MARKERS = {"a/l", "a/p", "s/o", "d/o", "bin", "binti", "bt", "bte"}


def short_name(full: str) -> str:
    """'Kavin a/l Raju' -> 'Kavin R.'; 'Meera Suresh' -> 'Meera S.'; one word stays as is."""
    words = full.split()
    if not words:
        return ""
    for index, word in enumerate(words):
        if index and word.lower() in PATRONYMIC_MARKERS:
            given, rest = words[:index], words[index + 1 :]
            break
    else:
        given, rest = words[:1], words[1:][-1:]
    initial = f" {rest[0][0].upper()}." if rest else ""
    return " ".join(given) + initial


class AchievementQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class Achievement(models.Model):
    """A pupil's or team's win, shown on the Achievements page."""

    ACADEMIC, SPORTS, ARTS, TAMIL, OTHER = "academic", "sports", "arts", "tamil", "other"
    CATEGORIES = [
        (ACADEMIC, _("Academic")),
        (SPORTS, _("Sports")),
        (ARTS, _("Arts and culture")),
        (TAMIL, _("Tamil language")),
        (OTHER, _("Other")),
    ]
    SCHOOL, DISTRICT, STATE, NATIONAL, INTERNATIONAL = (
        "school", "district", "state", "national", "international"
    )
    LEVELS = [
        (SCHOOL, _("School")),
        (DISTRICT, _("District")),
        (STATE, _("State")),
        (NATIONAL, _("National")),
        (INTERNATIONAL, _("International")),
    ]
    HIGH_LEVELS = {STATE, NATIONAL, INTERNATIONAL}

    title = models.CharField(
        max_length=200, help_text="e.g. “1st place, district Tamil essay competition”"
    )
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    level = models.CharField(max_length=20, choices=LEVELS)
    is_published = models.BooleanField("published", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AchievementQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portal:achievement_detail", args=[self.pk])

    def clean(self) -> None:
        require_one_language(self, "title", "Give the achievement a title in at least one language.")

    @property
    def is_high_level(self) -> bool:
        return self.level in self.HIGH_LEVELS

    @property
    def photos_allowed(self) -> bool:
        """Photos only when every pupil listed has their parents' agreement."""
        return all(pupil.consent for pupil in self.pupils.all())

    @property
    def pupil_line(self) -> str:
        return ", ".join(pupil.display for pupil in self.pupils.all())

    @property
    def consent_summary(self) -> str:
        pupils = list(self.pupils.all())
        if not pupils:
            return "no pupils listed"
        agreed = sum(pupil.consent for pupil in pupils)
        return "all agreed" if agreed == len(pupils) else f"{agreed} of {len(pupils)} agreed"


class AchievementPupil(models.Model):
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="pupils")
    name = models.CharField(max_length=100, help_text="As on the certificate.")
    class_name = models.CharField("class", max_length=30, blank=True, help_text="e.g. 5 Mutiara")
    consent = models.BooleanField(
        "parents agreed",
        default=False,
        help_text="Tick only if the parents agreed to their child's name and photo being shown.",
    )
    show_full_name = models.BooleanField(
        default=False, help_text="Otherwise only the first name and an initial are shown."
    )

    class Meta:
        ordering = ["pk"]
        verbose_name = "pupil"

    def __str__(self) -> str:
        return self.name

    @property
    def display(self) -> str:
        if not self.consent:
            year = re.search(r"\d", self.class_name)
            return _("a Year %(year)s pupil") % {"year": year[0]} if year else str(_("a pupil"))
        name = self.name.strip() if self.show_full_name else short_name(self.name)
        return f"{name} ({self.class_name.strip()})" if self.class_name.strip() else name


class AchievementPhoto(models.Model):
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="achievements/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "photo"

    def __str__(self) -> str:
        return self.caption or f"Photo {self.pk}"

    def save(self, *args, **kwargs) -> None:
        self.image = shrink_new_upload(self.image)
        super().save(*args, **kwargs)
```

`portal/translation.py`: register `Achievement` with `fields = ("title", "description")` and `AchievementPhoto` with `fields = ("caption",)` (both `AnyLanguage`). Run `.venv\Scripts\python manage.py makemigrations portal -n achievement`.

- [ ] **Step 4: Run** the tests. Expected: pass.
- [ ] **Step 5: Commit** "Add achievements with pupils and photos".

---

### Task 2: The Achievements pages

**Files:** Modify `portal/views.py`, `portal/urls.py`, `portal/templates/portal/base.html`, `portal/static/portal/style.css`, `tests/test_browser.py`, `tests/test_achievements.py`; create `portal/templates/portal/achievement_list.html`, `portal/templates/portal/achievement_detail.html`; translations.

**Interfaces — Consumes:** Task 1 models. **Produces:** URL names `portal:achievement_list` (`/achievements/`), `portal:achievement_detail` (`/achievements/<pk>/`); context `year`, `years` (list of `(year, url, is_current)`), `filters` (list of `(label, url, is_current)`), `achievements`.

- [ ] **Step 1: Failing tests** — append (add `from django.urls import reverse`):

```python
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
```

In `tests/test_browser.py`: create an achievement in the `site` fixture (Tamil title, one consented pupil with a long Tamil name, level State, today's date) and add `"/achievements/"` and its detail URL to `page_paths` (return it from the fixture as `site["achievement"]`).

- [ ] **Step 2: Run** — Expected: `NoReverseMatch` for `achievement_list`.

- [ ] **Step 3: Implement**
  - `base.html`: inside `<head>` after the stylesheet link add `{% block head %}{% endblock %}`; add the menu link after Documents (`{% url 'portal:achievement_list' %}`, `aria-current` when `"achievement" in current`, text `{% translate "Achievements" %}`) and the same link in the footer after Documents.
  - `portal/views.py` (import `Achievement`):

```python
ACHIEVEMENT_FILTERS = [("", gettext_lazy("All")), *Achievement.CATEGORIES]


def achievement_query(year: int | None, category: str) -> str:
    params = {}
    if year:
        params["year"] = year
    if category:
        params["type"] = category
    return "?" + urlencode(params)


def achievement_list(request):
    category = request.GET.get("type", "")
    if category not in dict(Achievement.CATEGORIES):
        category = ""
    achievements = Achievement.objects.published()
    if category:
        achievements = achievements.filter(category=category)
    years = [d.year for d in achievements.dates("date", "year", order="DESC")]
    chosen = request.GET.get("year", "")
    year = int(chosen) if chosen.isdigit() and int(chosen) in years else (years[0] if years else None)
    shown = achievements.filter(date__year=year).prefetch_related("pupils", "photos") if year else []
    return render(
        request,
        "portal/achievement_list.html",
        {
            "year": year,
            "achievements": list(shown),
            "years": [(y, achievement_query(y, category), y == year) for y in years],
            "filters": [
                (label, achievement_query(year, key), key == category)
                for key, label in ACHIEVEMENT_FILTERS
            ],
        },
    )


def achievement_detail(request, pk):
    achievement = get_object_or_404(
        Achievement.objects.published().prefetch_related("pupils", "photos"), pk=pk
    )
    return render(request, "portal/achievement_detail.html", {"achievement": achievement})
```

  - `portal/urls.py`: `path("achievements/", views.achievement_list, name="achievement_list"),` and `path("achievements/<int:pk>/", views.achievement_detail, name="achievement_detail"),`.
  - `achievement_list.html`:

```html
{% extends "portal/base.html" %}
{% load i18n %}

{% block title %}{% translate "Achievements" %}, {{ school_name }}{% endblock %}
{% block head %}<meta name="robots" content="noindex">{% endblock %}

{% block content %}
<header class="page-head">
  <h1>{% translate "Achievements" %}</h1>
  <nav class="tabs tabs--wrap" aria-label="{% translate 'Show only' %}">
    {% for label, url, current in filters %}<a href="{{ url }}"{% if current %} aria-current="page"{% endif %}>{{ label }}</a>{% endfor %}
  </nav>
</header>

{% if year %}
  <div class="month-head">
    <h2>{{ year }}</h2>
    {% if years|length > 1 %}
      <nav class="month-nav" aria-label="{% translate 'Years' %}">
        {% for y, url, current in years %}<a href="{{ url }}"{% if current %} aria-current="page"{% endif %}>{{ y }}</a>{% endfor %}
      </nav>
    {% endif %}
  </div>
  <ul class="achievements">
    {% for item in achievements %}
      <li class="achievement">
        {% if item.photos_allowed %}{% with photo=item.photos.all|first %}{% if photo %}<img src="{{ photo.image.url }}" alt="" loading="lazy">{% endif %}{% endwith %}{% endif %}
        <div>
          <p class="meta"><span class="level{% if item.is_high_level %} level--high{% endif %}">{{ item.get_level_display }}</span> · <time datetime="{{ item.date|date:'Y-m-d' }}">{{ item.date|date:"j F Y" }}</time></p>
          <h3><a href="{{ item.get_absolute_url }}">{{ item.title }}</a></h3>
          {% if item.pupil_line %}<p>{{ item.pupil_line }}</p>{% endif %}
        </div>
      </li>
    {% endfor %}
  </ul>
{% else %}
  <p class="meta">{% translate "No achievements yet." %}</p>
{% endif %}
{% endblock %}
```

  - `achievement_detail.html`:

```html
{% extends "portal/base.html" %}
{% load i18n %}

{% block title %}{{ achievement.title }}, {{ school_name }}{% endblock %}
{% block head %}<meta name="robots" content="noindex">{% endblock %}

{% block content %}
<article>
  <header class="page-head">
    <p class="meta"><span class="level{% if achievement.is_high_level %} level--high{% endif %}">{{ achievement.get_level_display }}</span> · {{ achievement.get_category_display }} · <time datetime="{{ achievement.date|date:'Y-m-d' }}">{{ achievement.date|date:"j F Y" }}</time></p>
    <h1>{{ achievement.title }}</h1>
    {% if achievement.pupil_line %}<p>{{ achievement.pupil_line }}</p>{% endif %}
  </header>
  {% if achievement.description %}<div class="prose">{{ achievement.description|linebreaks }}</div>{% endif %}
  {% if achievement.photos_allowed %}
    {% with photos=achievement.photos.all %}{% if photos %}
      <ul class="photos">
        {% for photo in photos %}
          <li><figure><a href="{{ photo.image.url }}"><img src="{{ photo.image.url }}" alt="{{ photo.caption }}" loading="lazy"></a>{% if photo.caption %}<figcaption>{{ photo.caption }}</figcaption>{% endif %}</figure></li>
        {% endfor %}
      </ul>
    {% endif %}{% endwith %}
  {% endif %}
  <p class="more"><a href="{% url 'portal:achievement_list' %}">{% translate "Back to all achievements" %}</a></p>
</article>
{% endblock %}
```

  - `style.css`, after the Contact block:

```css
/* Achievements */

.achievements { max-width: var(--measure); margin: 0; padding: 0; list-style: none; }
.achievement {
  display: grid;
  grid-template-columns: 6rem 1fr;
  gap: 1rem;
  padding-block: 1.1rem;
  border-top: 1px solid var(--rule);
}
.achievement:not(:has(img)) { grid-template-columns: 1fr; }
.achievement img { width: 6rem; height: 6rem; border-radius: var(--radius); object-fit: cover; }
.achievement h3 { margin: 0.2rem 0; }
.achievement p { margin: 0; }
.level { font-weight: 600; }
.level--high { padding: 0.05rem 0.45rem; border-radius: var(--radius); background: var(--blue); color: var(--white); }
```

  - Translations:

    | English | Tamil | Malay |
    |---|---|---|
    | Achievements | சாதனைகள் | Pencapaian |
    | Academic | கல்வி | Akademik |
    | Arts and culture | கலை மற்றும் பண்பாடு | Seni dan budaya |
    | Tamil language | தமிழ் மொழி | Bahasa Tamil |
    | Other | மற்றவை | Lain-lain |
    | School | பள்ளி | Sekolah |
    | District | மாவட்டம் | Daerah |
    | State | மாநிலம் | Negeri |
    | National | தேசியம் | Kebangsaan |
    | International | அனைத்துலகம் | Antarabangsa |
    | a Year %(year)s pupil | %(year)s ஆம் ஆண்டு மாணவர் ஒருவர் | seorang murid Tahun %(year)s |
    | a pupil | ஒரு மாணவர் | seorang murid |
    | Years | ஆண்டுகள் | Tahun |
    | No achievements yet. | இன்னும் சாதனைகள் இல்லை. | Belum ada pencapaian. |
    | Back to all achievements | அனைத்துச் சாதனைகளுக்கும் திரும்பு | Kembali ke semua pencapaian |

- [ ] **Step 4: Run** the full suite (browser tests included). Expected: all pass.
- [ ] **Step 5: Commit** "Add the Achievements page".

---

### Task 3: Admin, WhatsApp, Editors

**Files:** Modify `portal/admin.py`, `portal/whatsapp.py`, `portal/management/commands/setup_roles.py`, `tests/test_achievements.py`; create `portal/templates/portal/whatsapp/achievement.txt`.

**Interfaces — Consumes:** Task 1 models; `AnyLanguageAdmin`, `WhatsAppShareMixin`, `TranslationTabularInline`, `share_message`.

- [ ] **Step 1: Failing tests** — append (imports: `Group`, `User`, `call_command`, `share_message`):

```python
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
    html = admin_client.get(reverse("admin:portal_achievement_change", args=[item.pk])).content.decode()
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
```

- [ ] **Step 2: Run** — Expected: `KeyError` for `Achievement` in WhatsApp templates; `NoReverseMatch` for the admin; editor 403.

- [ ] **Step 3: Implement**
  - `portal/templates/portal/whatsapp/achievement.txt`:

    ```
    {% load i18n %}{% autoescape off %}*{{ post.title }}*{% if post.pupil_line %}
    {{ post.pupil_line }}{% endif %}

    {% translate "Details:" %} {{ url }}
    {% endautoescape %}
    ```

  - `portal/whatsapp.py`: import `Achievement`; add it to `TEMPLATES` and the type hints. `is_public` falls through to `obj.is_published` (no change needed beyond the hint).
  - `portal/admin.py` (import `Achievement`, `AchievementPhoto`, `AchievementPupil`):

```python
class AchievementPupilInline(admin.TabularInline):
    model = AchievementPupil
    extra = 3
    fields = ["name", "class_name", "consent", "show_full_name"]


class AchievementPhotoInline(TranslationTabularInline):
    model = AchievementPhoto
    extra = 2
    fields = ["image", "caption", "order"]


@admin.register(Achievement)
class AchievementAdmin(WhatsAppShareMixin, AnyLanguageAdmin):
    list_display = ["title", "date", "category", "level", "is_published", "consent", "whatsapp_share"]
    list_filter = ["category", "level", "is_published"]
    search_fields = in_all_languages("title") + ["pupils__name"]
    date_hierarchy = "date"
    readonly_fields = ["photo_note", "whatsapp_share"]
    inlines = [AchievementPupilInline, AchievementPhotoInline]

    @admin.display(description="parents agreed")
    def consent(self, obj):
        return obj.consent_summary

    @admin.display(description="photos")
    def photo_note(self, obj):
        if obj is None or obj.pk is None or obj.photos_allowed:
            return "Photos are shown on the site."
        return "Photos are hidden until every pupil listed has “parents agreed” ticked."
```

  - `setup_roles.py`: add `"achievement"`, `"achievementpupil"` and `"achievementphoto"`, each `["add", "change", "delete", "view"]`.

- [ ] **Step 4: Run** the full suite and both ruff checks. Expected: all pass.
- [ ] **Step 5: Commit** "Manage and share achievements in the admin".

---

### Task 4: Check it in the browser

- [ ] Add two sample achievements locally (one State-level with a photo and consented pupils, one with a pupil without consent), view `/achievements/` and a detail page at 360 px and 1280 px in Tamil and English, check the filter, year links, held-back photos and level label; delete the samples. Commit any CSS fix.
