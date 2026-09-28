# School portal

A website where school staff post events, news and photo albums, and parents can sign up
to get an email when an event is added.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py setup_roles        # creates the "Editors" staff group
python manage.py createsuperuser    # your own admin login
python manage.py runserver
```

Open http://127.0.0.1:8000 for the public site and http://127.0.0.1:8000/admin/ to manage it.

## Giving staff access

1. In the admin, go to **Users** and add a user.
2. Tick **Staff status** and add them to the **Editors** group.

Editors can add, edit and delete events, news, albums and photos, and see the subscriber list.

## Importing a term's events from a spreadsheet

1. In the admin, go to **Events** and click **Import from spreadsheet**.
2. Download the Excel template and fill in one event per row. Leave *Start time* empty for
   all-day events, and fill in *End date* for multi-day events like holidays or exam week.
   Dates are day-first (14/10/2026). CSV files (e.g. exported from Google Sheets) also work.
3. Upload the file. Rows with problems are listed with their row number; duplicates of events
   that already exist are skipped.
4. On the review page, correct anything, tick the events and click **Publish ticked events**.
   Tick **Email parents** to notify subscribers at the same time.

Imported events stay as drafts, invisible to parents, until they're published. Past uploads
are listed under **Event imports**.

## Emailing parents

Parents sign up at the bottom of the home page. To email them about an event, select it in
**Admin > Events**, choose **Email subscribers about selected events** and click **Go**.
Every email includes a link to stop future emails.

In development, emails are printed in the terminal instead of sent.

## Configuration

Set these environment variables in production:

| Variable | Purpose | Default |
|---|---|---|
| `SCHOOL_NAME` | Name shown on the site and in emails | `Our School` |
| `SITE_URL` | Public address, used for links in emails | `http://127.0.0.1:8000` |
| `DJANGO_TIME_ZONE` | School's time zone, e.g. `Asia/Kolkata`, `Europe/Berlin` | `Asia/Kuala_Lumpur` |
| `DJANGO_SECRET_KEY` | Long random secret | development-only value |
| `DJANGO_DEBUG` | `0` in production | `1` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated domain names | `localhost,127.0.0.1` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | SMTP server for sending emails. Without `EMAIL_HOST`, emails go to the console. | |
| `DEFAULT_FROM_EMAIL` | Sender address | `<SCHOOL_NAME> <noreply@example.com>` |

## Tests

```powershell
pytest
ruff check .
```
