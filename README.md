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
| `DJANGO_BEHIND_PROXY` | `1` behind PythonAnywhere or Cloudflare Tunnel, so the site knows visitors use https | `0` |
| `DJANGO_SERVE_MEDIA` | Serve uploaded photos from Django when `DJANGO_DEBUG` is `0` | `1` |
| `BACKUP_DIR`, `BACKUP_KEEP` | Where `manage.py backup` saves zips, and how many to keep | `backups\`, `14` |

## Hosting on PythonAnywhere (the live site)

The live site runs on a paid [PythonAnywhere](https://www.pythonanywhere.com/) account, user
`sjktldgsemenyih`, at https://sjktldgsemenyih.pythonanywhere.com. PythonAnywhere runs the web
server, gives the site `https://` and keeps it running, so there is no computer at school to
look after.

### Updating the live site

After new changes are pushed to GitHub, open a **Bash** console on PythonAnywhere (**Consoles**
tab) and run:

```bash
cd ~/Malar_school_site
git pull
~/.virtualenvs/school/bin/python -m pip install -r requirements.txt
~/.virtualenvs/school/bin/python manage.py migrate
~/.virtualenvs/school/bin/python manage.py setup_roles
~/.virtualenvs/school/bin/python manage.py collectstatic --noinput
```

Then click **Reload** on the **Web** tab. The site keeps running the old code until you do.

Always call Python by its full path as above. A plain `python` or `pip` in the console is
PythonAnywhere's general Python, not the site's, so packages installed with it don't reach the
site. Steps with nothing to do are harmless: `migrate` says "No migrations to apply" and `pip`
says "Requirement already satisfied".

### Setting it up from scratch

Only needed for a new account, or to rebuild the site.

1. In a **Bash** console:

   ```bash
   git clone https://github.com/rameshkkupusamy-png/Malar_school_site.git
   cd ~/Malar_school_site
   mkvirtualenv school --python=python3.12
   ~/.virtualenvs/school/bin/python -m pip install -r requirements.txt
   cp .env.example .env
   ~/.virtualenvs/school/bin/python -c "import secrets; print(secrets.token_urlsafe(50))"
   nano .env
   ```

2. In `.env`, fill in the Google values and the hosting lines (remove their `#`):

   ```
   DJANGO_DEBUG=0
   DJANGO_SECRET_KEY=<the long value printed above>
   DJANGO_ALLOWED_HOSTS=sjktldgsemenyih.pythonanywhere.com
   SITE_URL=https://sjktldgsemenyih.pythonanywhere.com
   DJANGO_BEHIND_PROXY=1
   ```

   Save with **Ctrl+O**, **Enter**, **Ctrl+X**. `SITE_URL` is used for the links in emails,
   WhatsApp messages and the calendar, so it must be the public address.

3. Set up the database and the site owner login:

   ```bash
   ~/.virtualenvs/school/bin/python manage.py migrate
   ~/.virtualenvs/school/bin/python manage.py setup_roles
   ~/.virtualenvs/school/bin/python manage.py createsuperuser
   ~/.virtualenvs/school/bin/python manage.py collectstatic --noinput
   ```

4. On the **Web** tab, choose **Add a new web app** > **Manual configuration** > **Python 3.12**.
   Then set:
   - **Virtualenv:** `/home/sjktldgsemenyih/.virtualenvs/school`
   - **Source code:** `/home/sjktldgsemenyih/Malar_school_site`
   - **WSGI configuration file:** open it, delete everything, and put in:

     ```python
     import os
     import sys

     path = "/home/sjktldgsemenyih/Malar_school_site"
     if path not in sys.path:
         sys.path.insert(0, path)
     os.environ["DJANGO_SETTINGS_MODULE"] = "school_portal.settings"

     from django.core.wsgi import get_wsgi_application

     application = get_wsgi_application()
     ```

   - **Static files:** URL `/static/` → `/home/sjktldgsemenyih/Malar_school_site/staticfiles`,
     and URL `/media/` → `/home/sjktldgsemenyih/Malar_school_site/media` (photos and documents).
   - **Security:** turn on **Force HTTPS**.

   Click **Reload** and open the site.

5. In Google Cloud Console, add
   `https://sjktldgsemenyih.pythonanywhere.com/accounts/google/login/callback/` to the client's
   **Authorised redirect URIs**.

### Backups

On the **Tasks** tab, add a daily scheduled task (for example at 02:00) that runs:

```bash
/home/sjktldgsemenyih/.virtualenvs/school/bin/python /home/sjktldgsemenyih/Malar_school_site/manage.py backup
```

Each backup is one zip file (the database, all photos and documents, and the private achievement photos in `private_media/`) in `backups/`, and the
newest 14 are kept (`BACKUP_KEEP`). The backups sit on the same account as the site, so now and
then download the newest zip from the **Files** tab and keep it somewhere else, such as the
school's Google Drive. To restore, unzip it, put `db.sqlite3`, `media/` and `private_media/` back in
`~/Malar_school_site`, and click **Reload**.

### If something goes wrong

The **Web** tab links to the **error log** and the **server log**. The last lines of the error
log usually name the problem. After any change to `.env`, click **Reload**.

## Alternative: hosting on a Windows computer

Not used for the live site. Kept in case the school ever moves the site to its own computer.

The site can also run on a spare Windows computer at home. Visitors reach it through
**Cloudflare Tunnel**: the computer connects out to Cloudflare, so nothing on the router
changes and the home network stays closed. Cloudflare also gives the site `https://`.

#### 1. Get a web address (once)

1. Create a free account at https://dash.cloudflare.com/.
2. Buy a domain, for example under **Domain Registration > Register Domains** in Cloudflare
   (roughly US$10 a year for a `.com` or `.org`). A `.edu.my` address has to be applied for by
   the school through MYNIC instead; it can be pointed at Cloudflare later.

#### 2. Prepare the computer (once)

1. In **Settings > System > Power**, set **Sleep** to **Never** when plugged in. In **Windows
   Update > Advanced options**, set **Active hours** to school hours so restarts happen at night.
2. Install Python 3.12 or newer from https://www.python.org/downloads/ (tick **Add python.exe
   to PATH**) and Git from https://git-scm.com/download/win.
3. In PowerShell:

   ```powershell
   cd C:\
   git clone https://github.com/rameshkkupusamy-png/Malar_school_site.git school-site
   cd C:\school-site
   python -m venv .venv
   .venv\Scripts\pip.exe install -r requirements.txt
   copy .env.example .env
   python -c "import secrets; print(secrets.token_urlsafe(50))"   # copy this for DJANGO_SECRET_KEY
   notepad .env
   ```

4. In `.env`, fill in the Google values and remove the `#` from the hosting lines, using your
   domain. Set `BACKUP_DIR` to a different drive or a synced cloud folder (e.g. OneDrive) if you
   have one.
5. Set up the database and the site owner login:

   ```powershell
   .venv\Scripts\python.exe manage.py migrate
   .venv\Scripts\python.exe manage.py setup_roles
   .venv\Scripts\python.exe manage.py createsuperuser
   .venv\Scripts\python.exe manage.py collectstatic --noinput
   .venv\Scripts\python.exe manage.py serve
   ```

   Open http://127.0.0.1:8000 on that computer to check it works, then press Ctrl+C.

#### 3. Connect it to your web address (once)

1. In Cloudflare, open **Zero Trust > Networks > Tunnels**, click **Create a tunnel**, choose
   **Cloudflared**, and name it `school-site`.
2. Pick **Windows**, and run the install command it shows in an **Administrator** PowerShell.
   This installs `cloudflared` as a Windows service that starts with the computer.
3. Add a **Public hostname**: your domain (and a second one for `www`), service type **HTTP**,
   URL `127.0.0.1:8000`.
4. In your domain's Cloudflare settings, turn on **SSL/TLS > Edge Certificates > Always Use
   HTTPS**.
5. In Google Cloud Console, add `https://<your-domain>/accounts/google/login/callback/` to the
   client's **Authorised redirect URIs**.

#### 4. Start the site with Windows

Open **Task Scheduler > Create Task**:

- **General:** name it `School site`, choose **Run whether user is logged on or not**.
- **Triggers:** **At startup**.
- **Actions:** start `C:\school-site\.venv\Scripts\python.exe` with arguments
  `manage.py serve` and **Start in** `C:\school-site`.
- **Settings:** untick **Stop the task if it runs longer than**, and tick **If the task fails,
  restart every 1 minute**.

Add a second task, `School site backup`, **Daily** at 2:00 AM, running the same Python with
`manage.py backup`. Each backup is one zip file (database plus all photos) in `BACKUP_DIR`; the
newest 14 are kept (`BACKUP_KEEP`). To restore, stop the site, unzip, and put `db.sqlite3` and
`media\` back in `C:\school-site`.

Restart the computer once and check the site opens from your phone.

#### Updating it

After new changes are pushed to GitHub, on the hosting computer:

```powershell
cd C:\school-site
git pull
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py setup_roles     # gives Editors access to any new sections
.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Then restart the **School site** task in Task Scheduler (right-click, **End**, then **Run**).

## Tests

```powershell
python -m playwright install chromium   # once, for the browser tests
pytest
ruff check .
```

`tests/test_browser.py` opens every public page in Chromium at phone and desktop width and fails
on page errors, sideways scrolling or a missing heading. Skip it with `pytest -m "not browser"`.

GitHub runs all of these checks on every push and pull request (`.github/workflows/ci.yml`).
