# School portal

Django 6.1 site where school staff publish events, news and photo albums, and parents
sign up for event emails. Staff edit everything in the Django admin (`/admin/`).

## Layout

- `school_portal/` project config (settings read from environment variables)
- `portal/` the app: models, views, admin, `notifications.py` (subscriber emails),
  `management/commands/setup_roles.py` (creates the "Editors" staff group)
- `portal/imports.py` spreadsheet import (parse .xlsx/.csv into draft events, build the template);
  the upload and review screens are custom admin views on `EventAdmin` (`get_urls`), templates in
  `portal/templates/admin/portal/event/`
- `portal/auth.py` staff sign-in rules (django-allauth): Google sign-in only for active
  `StaffMember` emails; password sign-up is closed. `import_staff` loads the list from a
  spreadsheet. The admin login page is `portal/templates/admin/staff_login.html`
- `portal/templates/portal/` templates; `_*.html` are partials
- `portal/static/portal/style.css` all styles
- `tests/` pytest-django tests
- Hosting: the live site runs on a Windows computer with `manage.py serve` (Waitress, localhost
  only) behind Cloudflare Tunnel; WhiteNoise serves static files, Django serves `media/`
  (`SERVE_MEDIA`). `manage.py backup` zips the database and photos. Steps are in the README.

## Commands (PowerShell, from the project root)

- Activate env: `.venv\Scripts\Activate.ps1`
- Install: `pip install -r requirements-dev.txt`
- Run: `python manage.py runserver` then open http://127.0.0.1:8000
- After model changes: `python manage.py makemigrations portal` then `python manage.py migrate`
- Tests: `pytest` (browser tests need `python -m playwright install chromium` once;
  skip them with `pytest -m "not browser"`)
- Lint/format: `ruff check .` and `ruff format .`

## Conventions

- Public pages only show `is_published` content; announcements also respect `published_at`
  (scheduling). Use the queryset helpers (`published()`, `upcoming()`, `past()`).
- All-day events: `Event.save()` normalizes them to local midnight through 23:59:59 on the end
  day. Build datetimes from date/time inputs with `imports.build_times()`.
- Imported events are always created unpublished; only the review page publishes them.
- Three languages: Tamil (default for every visitor, see `portal/middleware.py`), Malay, English.
  Wrap every user-facing string in `{% translate %}` / `gettext`, then run
  `scripts/translations.py update`, translate the new Tamil and Malay entries, and `compile`
  (GNU gettext isn't installed, so don't use makemessages). Untranslated Malay falls back to
  Tamil, not English, so never leave an entry empty.
- Post text (titles, bodies, locations, captions) uses django-modeltranslation
  (`portal/translation.py`): `title_ta`, `title_ms`, `title_en`, with at least one title required.
- Emails use Django 6.1 `MAILERS` / `mail.mailers.default`, not the deprecated `EMAIL_*`
  settings or `get_connection()`.
- Every feature gets tests in `tests/`. Run `pytest` and `ruff check .` before calling a change done.
  Hooks in `.claude/settings.json` enforce this: edited Python files are formatted with ruff, and
  the Stop hook runs ruff and pytest when code has changed. CI (`.github/workflows/ci.yml`) runs the
  same checks plus the migration and deploy checks.

## Design

Visual system for SJK (T) Ladang Semenyih, taken from the school crest
(`portal/static/portal/crest.png`). Keep new pages consistent:
- Colors: shield blue `#1E3F99` (headings, links, buttons), navy `#14295F` (footer, dark bands),
  torch yellow `#F2D53C` ("next", focus, buttons on dark bands), ribbon red `#C8413B` (pinned
  news only), ink `#16203A`, muted `#5A6378`, paper `#F6F7FA`, rule `#D8DCE6`. Tokens live in
  `style.css`.
- Type: Noto Serif Display italic for headings, Mukta Malar for body text. Both have Tamil
  fallbacks (Noto Serif Tamil, Mukta Malar), since staff may post in Tamil.
- The one bold element is the rounded line: it frames the full-width photo bands (`.band`,
  `.band-frame`) and runs down the centre of the `.split` sections between them. Keep the rest quiet.
- Home photos come from content, never from files in the code: the next event's image, else the
  newest published album's photos. Without photos the bands fall back to navy with a yellow corner.
- Avoid all-caps labels (Tamil has no case), arrows on links, sliders, identical card grids and
  decorative animation.
- Copy: plain, sentence case, written for parents; buttons say exactly what they do.
