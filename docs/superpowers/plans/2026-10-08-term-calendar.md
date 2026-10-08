# Term Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Events page becomes a month-by-month calendar with event types (Holiday, Exam, PIBG, Sports, Celebration), filters, and a Type column in the spreadsheet import.

**Architecture:** `Event.kind` plus `EventQuerySet.overlapping(start, end)` and a `month_range()` helper in `portal/models.py`. `event_list` picks the month and filter from the query string and renders one month. The shared `_event_row.html` partial shows the type label. `portal/imports.py` reads an optional Type column; the review form edits it.

**Tech Stack:** Django 6.1, django-modeltranslation, pytest-django, Playwright, openpyxl, `scripts/translations.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-term-calendar-design.md`

## Global Constraints

- Types (key → label): `event` Event (default), `holiday` Holiday, `exam` Exam, `pibg` PIBG, `sports` Sports, `celebration` Celebration.
- Filters, in order: All, Holidays, Exams, PIBG, Sports, Celebrations. Query `?month=YYYY-MM&type=<key>`; years 2000–2100; bad values fall back to the current month / All.
- A month shows published events with `starts_at < next month start` and (`ends_at >= month start`, or no end and `starts_at >= month start`), ordered by `starts_at`.
- Month boundaries are local midnight in `TIME_ZONE`.
- Empty month text: "No events this month." plus "Next: <Month YYYY>" link when a later month has events under the same filter.
- Unknown import type note: "Row N (title): the type 'x' wasn't recognised, so it was saved as Event."
- Every new phrase translated into Tamil and Malay (never empty); `scripts/translations.py update/compile`.
- Design: no arrows on the month links, no all-caps, quiet labels; only holidays get a tinted band.
- Tests: `.venv\Scripts\python -m pytest`, `ruff check .`, `ruff format --check .`.

## Review Focus

1. Six Tamil filter labels plus the month links must not make the page scroll sideways on a 360 px phone. Covered by the browser tests visiting `/events/?type=holiday` (Task 2).
2. A December–January holiday shows in both months, and January's "Previous month" goes to December of the previous year. Test in Task 2.
3. An event that starts at 00:30 local time on the 1st belongs to that month, not the previous one (UTC boundary). Test in Task 1.
4. Import Type cells with stray spaces or capitals ("  CUTI ") are recognised. Test in Task 3.
5. Existing events (created before the migration) keep working and show as plain events. Test in Task 1 (default kind).

---

### Task 1: Event types and month queries

**Files:** Modify `portal/models.py`, `portal/admin.py`; create migration `0011_event_kind` (generated); create `tests/test_term_calendar.py`.

**Interfaces — Produces:** `Event.EVENT/HOLIDAY/EXAM/PIBG/SPORTS/CELEBRATION`, `Event.KINDS`, field `kind`; `Event.objects.overlapping(start, end)`; `month_range(first_day: date) -> tuple[datetime, datetime]`.

- [ ] **Step 1: Failing tests** — create `tests/test_term_calendar.py`:

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from portal.models import Event, month_range

KL = ZoneInfo("Asia/Kuala_Lumpur")


def at(year, month, day, hour=9, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=KL)


@pytest.fixture
def event(db):
    def _make(title, start, end=None, **fields):
        return Event.objects.create(title=title, starts_at=start, ends_at=end, **fields)

    return _make


def test_new_events_are_plain_events(event):
    assert event("Assembly", at(2026, 10, 5)).kind == Event.EVENT


def test_month_range_is_local_midnight():
    start, end = month_range(date(2026, 12, 1))
    assert start == datetime(2026, 12, 1, tzinfo=KL)
    assert end == datetime(2027, 1, 1, tzinfo=KL)


def test_overlapping_finds_events_that_touch_the_month(event):
    event("In October", at(2026, 10, 5))
    event("Just after midnight on the 1st", at(2026, 10, 1, 0, 30))
    event("Holiday across months", at(2026, 9, 28), at(2026, 10, 2), all_day=True)
    event("December holiday", at(2026, 12, 21), at(2027, 1, 1), all_day=True)
    event("September", at(2026, 9, 10))

    october = {e.title for e in Event.objects.overlapping(*month_range(date(2026, 10, 1)))}
    january = {e.title for e in Event.objects.overlapping(*month_range(date(2027, 1, 1)))}

    assert october == {"In October", "Just after midnight on the 1st", "Holiday across months"}
    assert january == {"December holiday"}


def test_admin_lists_and_filters_by_type(event, admin_client):
    event("Cuti Deepavali", at(2026, 10, 20), kind=Event.HOLIDAY)
    event("Assembly", at(2026, 10, 5))

    url = reverse("admin:portal_event_changelist") + "?kind__exact=holiday"
    html = admin_client.get(url).content.decode()

    assert "Cuti Deepavali" in html
    assert "Assembly" not in html
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_term_calendar.py -q`. Expected: `ImportError: cannot import name 'month_range'`.

- [ ] **Step 3: Implement**

In `portal/models.py` add `from datetime import date, datetime, time` to the imports, then above `class EventQuerySet`:

```python
def month_range(first_day: date) -> tuple[datetime, datetime]:
    """Local midnight on the 1st of this month and of the next."""
    next_first = date(first_day.year + first_day.month // 12, first_day.month % 12 + 1, 1)
    return (
        timezone.make_aware(datetime.combine(first_day, time.min)),
        timezone.make_aware(datetime.combine(next_first, time.min)),
    )
```

In `EventQuerySet` add:

```python
    def overlapping(self, start, end):
        """Events running at some point between start and end (end not included)."""
        return self.filter(starts_at__lt=end).filter(
            Q(ends_at__gte=start) | Q(ends_at__isnull=True, starts_at__gte=start)
        )
```

In `class Event`, before `title`:

```python
    EVENT, HOLIDAY, EXAM, PIBG, SPORTS, CELEBRATION = (
        "event", "holiday", "exam", "pibg", "sports", "celebration"
    )
    KINDS = [
        (EVENT, _("Event")),
        (HOLIDAY, _("Holiday")),
        (EXAM, _("Exam")),
        (PIBG, _("PIBG")),
        (SPORTS, _("Sports")),
        (CELEBRATION, _("Celebration")),
    ]
```

and after the `all_day` field:

```python
    kind = models.CharField(
        "type",
        max_length=20,
        choices=KINDS,
        default=EVENT,
        help_text="Holidays and exams stand out on the Events page.",
    )
```

In `portal/admin.py` `EventAdmin`: insert `"kind"` after `"title"` in `list_display`, and add `"kind"` to the front of `list_filter`.

Run `.venv\Scripts\python manage.py makemigrations portal -n event_kind`.

- [ ] **Step 4: Run** the tests. Expected: pass.
- [ ] **Step 5: Commit** "Give events a type".

---

### Task 2: The month view

**Files:** Modify `portal/views.py`, `portal/templates/portal/event_list.html`, `portal/templates/portal/_event_row.html`, `portal/static/portal/style.css`, `tests/test_events.py`, `tests/test_languages.py`, `tests/test_browser.py`, `tests/test_term_calendar.py`; translations.

**Interfaces — Consumes:** `Event.KINDS`, `overlapping`, `month_range` (Task 1). **Produces:** context `month` (date), `events` (list), `filters` (list of `(label, url, is_current)`), `previous_url`, `next_url`, `next_month_with_events` (date or None), `next_month_with_events_url`.

- [ ] **Step 1: Failing tests** — append to `tests/test_term_calendar.py` (add `from django.utils import timezone`):

```python
def events_page(client, query=""):
    return client.get(reverse("portal:event_list") + query)


def test_page_opens_on_this_month(client, db):
    assert events_page(client).context["month"] == timezone.localdate().replace(day=1)


@pytest.mark.parametrize("query", ["?month=2026-13", "?month=junk", "?show=past", "?month=1999-01"])
def test_bad_or_old_links_show_this_month(client, db, query):
    assert events_page(client, query).context["month"] == timezone.localdate().replace(day=1)


def test_month_shows_events_spanning_into_it(event, client):
    event("December holiday", at(2026, 12, 21), at(2027, 1, 1), all_day=True, kind=Event.HOLIDAY)
    event("Exam week", at(2027, 1, 11), at(2027, 1, 15), all_day=True, kind=Event.EXAM)

    response = events_page(client, "?month=2027-01")

    assert [e.title for e in response.context["events"]] == ["December holiday", "Exam week"]
    html = response.content.decode()
    assert "January 2027" in html
    assert 'href="?month=2026-12"' in html
    assert 'href="?month=2027-02"' in html


def test_filter_shows_one_type_and_is_kept_between_months(event, client):
    event("Cuti", at(2026, 10, 20), all_day=True, kind=Event.HOLIDAY)
    event("Assembly", at(2026, 10, 5))

    response = events_page(client, "?month=2026-10&type=holiday")

    assert [e.title for e in response.context["events"]] == ["Cuti"]
    html = response.content.decode()
    assert 'href="?month=2026-11&amp;type=holiday"' in html
    assert 'aria-current="page">Holidays</a>' in html


def test_unknown_type_shows_everything(event, client):
    event("Assembly", at(2026, 10, 5))
    assert len(events_page(client, "?month=2026-10&type=nonsense").context["events"]) == 1


def test_empty_month_points_to_the_next_month_with_events(event, client):
    event("Exam week", at(2026, 12, 7), kind=Event.EXAM)

    html = events_page(client, "?month=2026-10").content.decode()
    assert "No events this month." in html
    assert '<a href="?month=2026-12">Next: December 2026</a>' in html

    html = events_page(client, "?month=2026-10&type=holiday").content.decode()
    assert "No events this month." in html
    assert "Next: " not in html


def test_type_labels_and_holiday_band(event, client):
    event("Cuti Deepavali", at(2026, 10, 20), all_day=True, kind=Event.HOLIDAY)
    event("UPSA", at(2026, 10, 12), kind=Event.EXAM)
    event("Assembly", at(2026, 10, 5))

    html = events_page(client, "?month=2026-10").content.decode()

    assert "event-row--holiday" in html
    assert '<p class="kind kind--exam">Exam</p>' in html
    assert html.count('<p class="kind') == 2


def test_drafts_stay_off_the_calendar(event, client):
    event("Draft trip", at(2026, 10, 5), is_published=False)
    assert events_page(client, "?month=2026-10").context["events"] == []
```

Update existing tests that relied on the tabs:
- `tests/test_events.py`: delete `test_event_list_past_tab` (replaced by the month tests).
- `tests/test_languages.py`: in `test_switcher_changes_the_language_and_remembers_it`, change `"Akan datang"` to `"Bulan depan"`.
- `tests/test_browser.py`: change `"/events/?show=past",` to `"/events/?type=holiday",`.

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_term_calendar.py -q`. Expected: the new tests fail (`KeyError: 'month'` / missing text).

- [ ] **Step 3: Implement**

`portal/views.py`: add `import re` and `from datetime import date, timedelta` (merge with the existing `timedelta` import), `from urllib.parse import quote, urlencode`, `from django.utils.translation import gettext_lazy`, and `month_range` to the `.models` import. Above `event_list`:

```python
MONTH_PARAM = re.compile(r"^(\d{4})-(\d{2})$")
FILTERS = [
    ("", gettext_lazy("All")),
    (Event.HOLIDAY, gettext_lazy("Holidays")),
    (Event.EXAM, gettext_lazy("Exams")),
    (Event.PIBG, gettext_lazy("PIBG")),
    (Event.SPORTS, gettext_lazy("Sports")),
    (Event.CELEBRATION, gettext_lazy("Celebrations")),
]


def chosen_month(value: str | None) -> date:
    """The month in ?month=YYYY-MM, or this month."""
    match = MONTH_PARAM.match(value or "")
    if match:
        year, month = int(match[1]), int(match[2])
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return date(year, month, 1)
    return timezone.localdate().replace(day=1)


def add_months(first_day: date, months: int) -> date:
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_query(first_day: date, kind: str) -> str:
    params = {"month": f"{first_day:%Y-%m}"}
    if kind:
        params["type"] = kind
    return "?" + urlencode(params)
```

Replace `event_list` with:

```python
def event_list(request):
    month = chosen_month(request.GET.get("month"))
    kind = request.GET.get("type", "")
    if kind not in {key for key, _label in FILTERS}:
        kind = ""

    events = Event.objects.published()
    if kind:
        events = events.filter(kind=kind)
    start, end = month_range(month)
    month_events = list(events.overlapping(start, end).order_by("starts_at"))

    next_month_with_events = None
    if not month_events:
        later = events.filter(starts_at__gte=end).order_by("starts_at").first()
        if later:
            next_month_with_events = timezone.localtime(later.starts_at).date().replace(day=1)

    # Calendar apps subscribe with webcal://, so phones keep checking for new events.
    feed = settings.SITE_URL + reverse("portal:calendar_feed")
    webcal = "webcal://" + feed.split("://", 1)[-1]
    return render(
        request,
        "portal/event_list.html",
        {
            "month": month,
            "events": month_events,
            "filters": [(label, month_query(month, key), key == kind) for key, label in FILTERS],
            "previous_url": month_query(add_months(month, -1), kind),
            "next_url": month_query(add_months(month, 1), kind),
            "next_month_with_events": next_month_with_events,
            "next_month_with_events_url": (
                month_query(next_month_with_events, kind) if next_month_with_events else ""
            ),
            "webcal_url": webcal,
            "google_calendar_url": "https://calendar.google.com/calendar/r?cid="
            + quote(webcal, safe=""),
        },
    )
```

`portal/templates/portal/event_list.html` — replace everything above the `<section class="calendar-subscribe"` block with:

```html
{% extends "portal/base.html" %}
{% load i18n %}

{% block title %}{% translate "Events" %}, {{ school_name }}{% endblock %}

{% block content %}
<header class="page-head">
  <h1>{% translate "Events" %}</h1>
  <nav class="tabs tabs--wrap" aria-label="{% translate 'Show only' %}">
    {% for label, url, current in filters %}<a href="{{ url }}"{% if current %} aria-current="page"{% endif %}>{{ label }}</a>{% endfor %}
  </nav>
</header>

<section class="month" aria-labelledby="month-title">
  <div class="month-head">
    <h2 id="month-title">{{ month|date:"F Y" }}</h2>
    <nav class="month-nav" aria-label="{% translate 'Months' %}">
      <a href="{{ previous_url }}">{% translate "Previous month" %}</a>
      <a href="{{ next_url }}">{% translate "Next month" %}</a>
    </nav>
  </div>
  {% if events %}
    <ul class="event-list">
      {% for event in events %}{% include "portal/_event_row.html" %}{% endfor %}
    </ul>
  {% else %}
    <p class="meta">{% translate "No events this month." %}{% if next_month_with_events %} <a href="{{ next_month_with_events_url }}">{% blocktranslate with month=next_month_with_events|date:"F Y" %}Next: {{ month }}{% endblocktranslate %}</a>{% endif %}</p>
  {% endif %}
</section>
```

(keep the existing calendar-subscribe section and `{% endblock %}` below it).

`portal/templates/portal/_event_row.html`:

```html
<li class="event-row{% if event.kind == 'holiday' %} event-row--holiday{% endif %}">
  {% include "portal/_datestamp.html" %}
  <div>
    {% if event.kind != "event" %}<p class="kind kind--{{ event.kind }}">{{ event.get_kind_display }}</p>{% endif %}
    <h3><a href="{{ event.get_absolute_url }}">{{ event.title }}</a></h3>
    <p class="meta">{% include "portal/_event_time.html" %}</p>
    {% if event.location %}<p class="meta">{{ event.location }}</p>{% endif %}
  </div>
</li>
```

`portal/static/portal/style.css` — after `.event-row .meta { … }`:

```css
/* Event types: only holidays get a band; exams a blue label; the rest a quiet label. */
.event-row--holiday,
.event-row--holiday:first-child {
  padding: 1rem 0.75rem;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--torch) 22%, var(--white));
}

.kind { margin: 0 0 0.2rem; color: var(--muted); font-size: var(--step--1); font-weight: 600; }
.kind--holiday { color: var(--navy); }
.kind--exam {
  display: inline-block;
  padding: 0.05rem 0.5rem;
  border-radius: var(--radius);
  background: var(--blue);
  color: var(--white);
}
```

and after `.tabs a[aria-current="page"] { … }`:

```css
.tabs--wrap { flex-wrap: wrap; column-gap: 1.25rem; }

.month-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem 1.5rem;
  margin-bottom: 1.25rem;
}

.month-head h2 { margin: 0; }
.month-nav { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; font-weight: 600; }
```

Remove the now-unused `Paginator` use from `event_list` only (announcements and albums still use it).

Translations (`update`, fill, `compile`):

| English | Tamil | Malay |
|---|---|---|
| Event | நிகழ்வு | Acara |
| Holiday | விடுமுறை | Cuti |
| Exam | தேர்வு | Peperiksaan |
| PIBG | PIBG | PIBG |
| Sports | விளையாட்டு | Sukan |
| Celebration | கொண்டாட்டம் | Perayaan |
| All | அனைத்தும் | Semua |
| Holidays | விடுமுறைகள் | Cuti |
| Exams | தேர்வுகள் | Peperiksaan |
| Celebrations | கொண்டாட்டங்கள் | Perayaan |
| Show only | இவற்றை மட்டும் காட்டு | Tunjukkan sahaja |
| Months | மாதங்கள் | Bulan |
| Previous month | முந்தைய மாதம் | Bulan sebelumnya |
| Next month | அடுத்த மாதம் | Bulan depan |
| No events this month. | இந்த மாதம் நிகழ்வுகள் இல்லை. | Tiada acara bulan ini. |
| Next: %(month)s | அடுத்து: %(month)s | Seterusnya: %(month)s |

- [ ] **Step 4: Run** the full suite. Expected: all pass, including browser tests and `test_every_phrase_has_a_translation`.
- [ ] **Step 5: Commit** "Show events month by month with type filters".

---

### Task 3: Type in the spreadsheet import

**Files:** Modify `portal/imports.py`, `portal/forms.py`, `portal/admin.py` (import and review views), `portal/templates/admin/portal/event/import_review.html`, `tests/test_import.py`.

**Interfaces — Consumes:** `Event.KINDS` and constants. **Produces:** `ParsedEvent.kind: str`, `parse_kind(value) -> str | None`, `DraftEventForm.kind`.

- [ ] **Step 1: Failing tests** — append to `tests/test_import.py` (it already sets `MEDIA_ROOT` and has `csv_file`):

```python
def test_import_reads_the_type_in_three_languages(db):
    result = parse_file(
        csv_file(
            "Title,Start date,Type\n"
            "Cuti Deepavali,20/10/2026,  CUTI \n"
            "UPSA,12/10/2026,தேர்வு\n"
            "Sports day,15/10/2026,Sports\n"
            "Assembly,5/10/2026,\n"
        )
    )
    assert [e.kind for e in result.events] == ["holiday", "exam", "sports", "event"]
    assert result.errors == []


def test_unknown_type_becomes_event_with_a_note(db):
    result = parse_file(csv_file("Title,Start date,Type\nBook fair,20/10/2026,Pameran\n"))
    assert result.events[0].kind == "event"
    assert result.errors == [
        "Row 2 (Book fair): the type 'Pameran' wasn't recognised, so it was saved as Event."
    ]


def test_template_has_a_type_column():
    sheet = load_workbook(io.BytesIO(build_template())).active
    assert [cell.value for cell in sheet[1]][-1] == "Type"


def test_imported_type_is_saved_and_can_be_changed_on_review(admin_client):
    admin_client.post(
        reverse("admin:portal_event_import"),
        {"file": csv_file("Title,Start date,Type\nCuti Deepavali,20/10/2026,Cuti\n"), "language": "ms"},
    )
    event = Event.objects.get()
    assert event.kind == Event.HOLIDAY
    assert not event.is_published

    admin_client.post(
        reverse("admin:portal_event_import_review", args=[event.source_import_id]),
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-event_id": str(event.pk),
            "form-0-title": "Cuti Deepavali",
            "form-0-start_date": "2026-10-20",
            "form-0-kind": Event.EXAM,
            "action": "save",
        },
    )
    event.refresh_from_db()
    assert event.kind == Event.EXAM
```

(Import `build_template`, `parse_file` and `Event` at the top of the file if they aren't already.)

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_import.py -q`. Expected: the new tests fail (`AttributeError: 'ParsedEvent' object has no attribute 'kind'`, template's last heading is "Description").

- [ ] **Step 3: Implement**

`portal/imports.py`:
- `COLUMNS = [..., "Description", "Type"]`.
- Below `TIME_FORMATS`:

```python
KIND_WORDS = {
    Event.HOLIDAY: ["holiday", "holidays", "cuti", "விடுமுறை"],
    Event.EXAM: ["exam", "exams", "examination", "test", "peperiksaan", "ujian", "தேர்வு", "பரீட்சை"],
    Event.PIBG: ["pibg", "pta", "பெற்றோர் ஆசிரியர் சங்கம்"],
    Event.SPORTS: ["sports", "sport", "sukan", "விளையாட்டு"],
    Event.CELEBRATION: ["celebration", "perayaan", "sambutan", "கொண்டாட்டம்", "விழா"],
    Event.EVENT: ["event", "acara", "நிகழ்வு"],
}
WORD_TO_KIND = {word: kind for kind, words in KIND_WORDS.items() for word in words}


def parse_kind(value) -> str | None:
    """The event type for a Type cell, Event when empty, or None if it isn't recognised."""
    text = " ".join(str(value or "").split()).lower()
    return WORD_TO_KIND.get(text) if text else Event.EVENT
```

- `ParsedEvent`: add `kind: str = Event.EVENT` after `description`.
- In `parse_file`, just before `result.events.append(`:

```python
        kind = parse_kind(cell("Type"))
        if kind is None:
            result.errors.append(
                f"Row {row_number} ({title}): the type '{cell('Type')}' wasn't recognised, "
                "so it was saved as Event."
            )
            kind = Event.EVENT
```

  and pass `kind=kind` to `ParsedEvent(...)`.
- `build_template`: widths `[34, 14, 12, 14, 12, 22, 50, 14]`; add the help line `["Type: Holiday, Exam, PIBG, Sports or Celebration (Cuti, Peperiksaan, Sukan, Perayaan also work). Leave empty for an ordinary event."]` after the multi-day line; add `""` as Type in the Science fair example and `"Holiday"` in the Diwali example.

`portal/admin.py` `import_view`: pass `kind=parsed.kind` to `Event.objects.create(...)`. `_import_review`: set `event.kind = row["kind"]` next to `event.location = row["location"]`.

`portal/forms.py`: import `Event` from `.models`; in `DraftEventForm` add `kind = forms.ChoiceField(choices=Event.KINDS)` after `location`, and `"kind": event.kind,` in `initial_for`.

`import_review.html`: add `<th scope="col">Type</th>` after Location in the header and `<td>{{ form.kind }}{{ form.kind.errors }}</td>` after the location cell.

- [ ] **Step 4: Run** the full suite and both ruff checks. Expected: all pass.
- [ ] **Step 5: Commit** "Read the event type from the spreadsheet import".

---

### Task 4: Check it in the browser

- [ ] Add sample events locally (a December–January holiday, an exam week, a PIBG meeting, a plain event), view `/events/?month=…` at 360 px and 1280 px in Tamil and English, check the filters, month links and holiday band, then delete the samples. Commit any CSS fix.
