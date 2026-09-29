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

Teachers sign in with their Google account. Only emails on the staff list can get in.

1. In the admin, go to **Staff members** and add the teacher's email (their name is optional).
   To add many at once, click **Import from spreadsheet** on that page and upload an Excel or CSV
   file with one person per row (their email, and their name if you like). The same import is
   available as `python manage.py import_staff teachers.xlsx`.
2. The teacher opens `/admin/`, clicks **Sign in with Google** and picks that account. The first
   time, their staff account is created automatically in the **Editors** group.

To remove someone, untick **Can sign in** (or use **Remove sign-in access** on the list). They
are signed out straight away. Only superusers can change the staff list.

Editors can add, edit and delete events, news, albums and photos, and see the subscriber list.
The username and password login stays on the same page for the site owner.

### Setting up Google sign-in (once)

1. Go to https://console.cloud.google.com/ and create a project, for example "Malar school site".
2. Open **Google Auth Platform**. Under **Branding**, set the app name and a support email. Under
   **Audience**, choose **External** and click **Publish app**, so any listed teacher's Google
   account works (in testing mode only named test users can sign in). The site only asks for
   name and email, so Google doesn't need to review it.
3. Under **Clients**, create a **Web application** client. Add these **Authorised redirect URIs**:
   - `http://127.0.0.1:8000/accounts/google/login/callback/` (for trying it out locally)
   - `https://<your-domain>/accounts/google/login/callback/` (once the site is live)
4. Copy `.env.example` to `.env` in the project folder and paste the client ID and secret after
   `GOOGLE_CLIENT_ID=` and `GOOGLE_CLIENT_SECRET=`. `.env` is git-ignored, so the secret stays on
   this computer. On a hosting server, set them as environment variables instead. Keep the secret
   out of the code and out of chat messages.

The **Sign in with Google** button appears once `GOOGLE_CLIENT_ID` is set.

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

## Languages: Tamil, Malay and English

Everyone sees the site in Tamil first. The **தமிழ் | BM | EN** buttons in the header switch
language, and the site remembers the choice. The admin starts in English.

- **Posts:** news, events and albums have a Tamil, Malay and English box for the title and
  text. Fill in at least one. Parents see their language, or another version if theirs is
  empty (Tamil first, then Malay, then English).
- **Spreadsheet imports:** pick the spreadsheet's language on the import page.
- **Emails to parents** use the language they were reading the site in when they signed up.

The site's own wording (menus, buttons, dates) lives in `locale/ta/LC_MESSAGES/django.po` and
`locale/ms/LC_MESSAGES/django.po`. After changing wording in a template or in code:

```powershell
.venv\Scripts\python.exe scripts\translations.py update    # adds new phrases to the .po files
# translate the new entries (msgstr) in both .po files
.venv\Scripts\python.exe scripts\translations.py compile   # builds the .mo files Django reads
```

A test fails if any phrase is left untranslated.

## Emailing parents

Parents sign up at the bottom of the home page. To email them about an event, select it in
**Admin > Events**, choose **Email subscribers about selected events** and click **Go**.
Every email includes a link to stop future emails.

In development, emails are printed in the terminal instead of sent.

## Configuration

Set these environment variables in production:

| Variable | Purpose | Default |
|---|---|---|
| `SCHOOL_NAME` | Name shown on the site and in emails | `SJK (T) Ladang Semenyih` |
| `SCHOOL_MOTTO` | Motto shown in the footer | `Usaha Tangga Kejayaan` |
| `SITE_URL` | Public address, used for links in emails | `http://127.0.0.1:8000` |
| `DJANGO_TIME_ZONE` | School's time zone, e.g. `Asia/Kolkata`, `Europe/Berlin` | `Asia/Kuala_Lumpur` |
| `DJANGO_SECRET_KEY` | Long random secret | development-only value |
| `DJANGO_DEBUG` | `0` in production | `1` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated domain names | `localhost,127.0.0.1` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | SMTP server for sending emails. Without `EMAIL_HOST`, emails go to the console. | |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in for staff (see above). Without them, only password login is shown. | |
| `DEFAULT_FROM_EMAIL` | Sender address | `<SCHOOL_NAME> <noreply@example.com>` |

## Tests

```powershell
python -m playwright install chromium   # once, for the browser tests
pytest
ruff check .
```

`tests/test_browser.py` opens every public page in Chromium at phone and desktop width and fails
on page errors, sideways scrolling or a missing heading. Skip it with `pytest -m "not browser"`.

GitHub runs all of these checks on every push and pull request (`.github/workflows/ci.yml`).
