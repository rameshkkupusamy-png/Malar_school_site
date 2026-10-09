# Urgent notice banner: design

Date: 2026-10-09. Status: agreed in chat.

## Goal

On days that worry parents — floods, haze, sudden closures — staff put one line at the top of
every page within a minute, and can share it to the parents' WhatsApp group.

## What parents see

- A navy bar across the top of every page, above the site header: a yellow "Urgent" label, the
  message, and a "Details" link when staff gave one.
- Shown from "Show from" until "Show until", only while published. Several current notices show
  together, newest first.
- The message appears in the parent's language, falling back to whatever staff wrote (like other
  posts). No close button; notices are short-lived.
- Colours: navy band, white text, torch-yellow label (red stays reserved for pinned news).

## What staff do

New "Urgent notices" section in the admin.

| Field | Notes |
|---|---|
| Message | One line, up to 200 characters, Tamil/Malay/English, at least one |
| Link | Optional, a full `http(s)` address (a page on this site, a document, …) |
| Show from | Default: now |
| Show until | Required. Default: 23:59 today (school time). Must be after Show from |
| Published | Ticked by default |

- List: message, show from, show until, published, "showing now" (yes/no), WhatsApp button.
- WhatsApp button only while the notice is showing. Message (site language, Tamil):
  `*<Urgent>:* <message>` then the link, or the home page if there is no link.
- Editors get add, change, delete and view (`setup_roles`).

## Not included

Emailing subscribers about a notice (later, once school email works); a close button; scheduling
repeats.

## Building blocks

- `portal/models.py`: `UrgentNotice`, `UrgentNoticeQuerySet.showing()`, `end_of_today()` default.
- `portal/translation.py`: `message`. Migration `0013`.
- `portal/context_processors.py`: `urgent_notices` (one query per page).
- `portal/templates/portal/base.html`: the bar before the header; `style.css`.
- `portal/admin.py`: `UrgentNoticeAdmin(WhatsAppShareMixin, AnyLanguageAdmin)`.
- `portal/whatsapp.py` + `portal/templates/portal/whatsapp/urgent.txt`.
- Translations: "Urgent", "Urgent notices", "Details".

## Tests

Showing window and published flag; several at once; "Details" link; message language fallback;
validation (end after start, a message in one language, link scheme); WhatsApp button and
message; Editors' permissions; browser tests at 360 px with a long Tamil notice.
