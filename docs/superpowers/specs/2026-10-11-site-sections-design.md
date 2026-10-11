# Pausing site sections: design

Date: 2026-10-11. Status: agreed in chat.

## Goal

Let the head admin pause a section of the public site for a while (for example while its content is
being fixed) and switch it back on later, from the admin, without a deploy.

Decisions made in chat: the purpose is a temporary pause, not hiding unused sections or reusing the
code for other schools; only superusers can switch sections; a paused page shows a short message
rather than "not found"; switchable sections are News, Events, Photos, Documents, PIBG,
Achievements and Search; settings live in one record (like `SchoolContact`), not one row per
section or environment variables.

Success: a superuser unticks a section, saves, and parents immediately stop seeing it anywhere on
the site (menu, footer, home page, search, links from other pages); ticking it again brings it
all back. Nothing is deleted, and Editors can keep preparing posts while it is paused.

## What parents see

- A paused section's links disappear from the top menu and the footer.
- Every page of a paused section, including old links shared on WhatsApp, answers with HTTP 503
  and the page `portal/section_paused.html`: heading "This section is not available right now",
  the line "Please check back later.", and links "Go to the home page" and "Contact the school".
  The page has `<meta name="robots" content="noindex">`. 503 (not 404) so search engines treat it
  as temporary.
- Home page:
  - News paused: no news parts; the next event leads the page as it already does with no news.
  - Events paused: no hero event, no "Coming up", no email sign-up box.
  - Photos paused: album photos are not used for the hero or the photo band (the bands fall back
    to navy as they already do without photos); no featured album link. An event's own image is
    still used when Events is on.
- Search: sections whose part of the site is paused are left out of the results (events, news,
  documents, achievements, photos). With Search paused, `/search/` shows the paused page.
- Links between sections are hidden when their target is paused: the PIBG page's "All PIBG
  events" link (Events), "All news" / "All upcoming events" on the home page, and any other
  `{% url %}` into a switchable section outside that section's own templates.
- Always on: the home page, the contact page, the urgent notice banner, unsubscribe links, the
  admin, and the web app manifest.

Which URLs each section covers:

| Section      | Key            | Views                                                                   |
|--------------|----------------|-------------------------------------------------------------------------|
| News         | `news`         | `announcement_list`, `announcement_detail`                              |
| Events       | `events`       | `event_list`, `event_detail`, `event_calendar`, `calendar_feed`, `subscribe` |
| Photos       | `photos`       | `album_list`, `album_detail`                                            |
| Documents    | `documents`    | `document_list`, `document_open`                                        |
| PIBG         | `pibg`         | `pibg`                                                                  |
| Achievements | `achievements` | `achievement_list`, `achievement_detail`, `private_media`               |
| Search       | `search`       | `search`                                                                |

`private_media` only serves achievement photos, so it follows Achievements. A paused `subscribe`
POST shows the paused page and creates no subscriber.

## Emails

While Events is paused, `notify_subscribers` and `send_reminders` send nothing and return 0.
Nothing is queued: when Events comes back on, only emails triggered after that are sent
(reminders resume for events still ahead). Existing subscribers stay subscribed; unsubscribe keeps
working.

In the admin, the "email subscribers" action and the import review's "email parents" option add
the warning "Events is paused, so no emails were sent." when Events is paused.

## Data

- `SiteSections` (one record, `pk` always 1, `load()` like `SchoolContact`), BooleanFields all
  `default=True`: `news`, `events`, `photos`, `documents`, `pibg`, `achievements`, `search`. Each
  has a verbose name (the section name) and help text saying what pausing hides, e.g. Events:
  "Also stops email sign-ups, event emails and reminders." Untranslated: only the admin sees it.
- Migration creates the table only; with no row, `load()` returns an unsaved record with all
  sections on, so the site is unchanged after deploy.

## Admin

- `SiteSectionsAdmin(SingleRecordAdmin)`, titled "Site sections": no second record, no delete.
- Superusers only: `has_module_permission`, `has_view_permission` and `has_change_permission`
  return `request.user.is_superuser`. `setup_roles` gives Editors nothing on `sitesections`.
- The WhatsApp share button (`whatsapp.is_public`) treats a post whose section is paused as not
  public, so staff see the existing "not public yet" state instead of sharing a dead link.

## Code

- `portal/sections.py`: `KEYS` (the seven keys above), `is_on(key) -> bool`, and the decorator
  `section(key)` that renders `portal/section_paused.html` with status 503 when the key is off.
  Applied to every view in the table.
- `portal/context_processors.school` adds `sections` (the `SiteSections` record, loaded lazily),
  used as `{% if sections.events %}` in `base.html` (menu, footer) and cross-section links.
- `views.home` skips the queries and context for paused sections; `search.find()` skips paused
  sections.
- One database read per request for the record is acceptable; no caching.
- New strings wrapped for translation, Tamil and Malay filled in, compiled.

## Tests (`tests/test_sections.py`)

- Default: no record, every section on; every switchable page answers 200.
- For each key: pausing it hides its menu and footer links and every view in its row answers 503
  with the paused text and `noindex`; other sections still answer 200.
- Paused `subscribe` POST creates no subscriber.
- Home page with News, Events and Photos each paused shows none of that section's parts; the
  sign-up box is gone with Events paused.
- Search leaves out paused sections' results; PIBG page hides "All PIBG events" with Events paused.
- `notify_subscribers` and `send_reminders` send no mail with Events paused; the admin action shows
  the warning.
- Admin: a superuser can open and save Site sections; an Editors member (after `setup_roles`)
  cannot see or open it; no add once saved, no delete.
- `is_public` is false for a published event while Events is paused.
- Browser sweep (`tests/test_browser.py`): the paused page in Tamil at phone width, no sideways
  scroll.

## Out of scope

Scheduled pauses (switch off on a date), a staff-written reason on the paused page, pausing the
home or contact page, pausing email sign-up separately from Events, and per-school configuration.
