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
- `portal/templates/portal/` templates; `_*.html` are partials
- `portal/static/portal/style.css` all styles
- `tests/` pytest-django tests

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
- Emails use Django 6.1 `MAILERS` / `mail.mailers.default`, not the deprecated `EMAIL_*`
  settings or `get_connection()`.
- Every feature gets tests in `tests/`. Run `pytest` and `ruff check .` before calling a change done.
  Hooks in `.claude/settings.json` enforce this: edited Python files are formatted with ruff, and
  the Stop hook runs ruff and pytest when code has changed. CI (`.github/workflows/ci.yml`) runs the
  same checks plus the migration and deploy checks.

## Design

Visual system (keep new pages consistent):
- Colors: bottle green `#1F4D3A`, marker yellow `#F2C14E` (only for "next"/"pinned"/focus),
  ink `#1B2421`, muted `#5E6B66`, paper `#F7F8F6`, rule `#D9DED9`. Tokens live in `style.css`.
- Type: Bricolage Grotesque for headings and date stamps, Lexend for body text.
- The big date stamp on the home page is the one bold element; keep everything else quiet.
- Avoid all-caps labels, arrows on links, identical card grids and decorative animation.
- Copy: plain, sentence case, written for parents; buttons say exactly what they do.
