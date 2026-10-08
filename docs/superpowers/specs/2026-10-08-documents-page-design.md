# Documents page: design

Date: 2026-10-08. Status: agreed in chat, waiting for review of this write-up.

## Goal

Parents find circulars, forms, timetables and school documents in one place on the site
instead of searching old WhatsApp messages. Staff upload a file in the admin, and can share it
to the parents' WhatsApp group in one tap.

Decisions made with the school:

- All four kinds of file go on the page: circulars (surat edaran), forms, timetables and lists,
  and school documents.
- Old files leave the page through an optional "remove after" date.
- One file per document. Its title and note can be written in Tamil, Malay and/or English like
  other posts; the file itself is often already bilingual.
- Files are uploaded to the site (stored in `media/`), not linked from Google Drive. The live
  site is on a paid PythonAnywhere plan, so disk space is not a concern.
- Documents get the "Share on WhatsApp" button too.

## What parents see

- "Documents" (Tamil ஆவணங்கள்) in the top menu and the footer, after Photos.
- `/documents/` lists published documents under four headings, always in this order:
  Circulars, Forms, Timetables and lists, School documents. A heading with no documents is
  hidden. With no documents at all, the page says "No documents yet."
- Within a heading, newest first.
- Each document shows its title (the link), the optional one-line note, the date it was added,
  and the file type and size, e.g. "PDF, 340 KB".
- Opening a document goes through `/documents/<pk>/`, which redirects to the current file.
  PDFs open in the phone's own viewer.
- A document stops being listed after the end of its "remove after" day (school time zone).

## What staff do

New "Documents" section in the admin.

| Field | Notes |
|---|---|
| Title | Tamil, Malay, English; at least one required |
| Note | Optional, one line (max 200 characters), three languages |
| Group | Circulars, Forms, Timetables and lists, School documents |
| File | pdf, doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png; max 10 MB |
| Remove after | Optional date; empty means it stays on the page |
| Published | Ticked by default |
| Added | Set automatically; shown to parents |

- Wrong type: "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file."
- Too big: "This file is 14 MB. The limit is 10 MB. Try saving the PDF at a smaller size."
- List: title, group, added, remove after, published (editable in the list), WhatsApp button.
  Filter by group and published; search titles and notes in all three languages.
- Editors (`setup_roles`) get add, change, delete and view on documents.

## Links and files

- `/documents/<pk>/` is the permanent link, used on the page and in WhatsApp messages.
  - Published document: redirects to the file, also after its "remove after" date, so links in
    older WhatsApp messages keep working.
  - Unpublished or deleted document: 404.
- Uploading a corrected file replaces the old one, and the old file is deleted from disk. The
  permanent link then opens the new file.
- Deleting a document deletes its file from disk.
- The file's direct `/media/documents/…` address is not secret, as with photos. Unpublishing
  hides the document from the page and the permanent link only.

## WhatsApp sharing

Uses `portal/whatsapp.py` with a new `portal/whatsapp/document.txt` template, in the site's
default language like the other messages:

```
*{title}*
{note, if any}

{"Open the document:"} {SITE_URL}/documents/{pk}/
```

The button shows only while the document is listed on the page (published and not past its
"remove after" date); otherwise the admin shows why it can't be shared.

## Building blocks

- `portal/models.py`: `Document` model and `DocumentQuerySet.published()` (published, and
  "remove after" empty or today or later in local time). `clean()` requires a title in one
  language. File checks are validators on the field (extension allow-list and size).
  Signals delete files on delete and on replace.
- `portal/translation.py`: register `title` and `note`.
- Migration `0009`.
- `portal/views.py` / `portal/urls.py`: `document_list` (`/documents/`) and `document_open`
  (`/documents/<pk>/`).
- `portal/templates/portal/document_list.html`; nav and footer links in `base.html`.
- `portal/admin.py`: `DocumentAdmin(WhatsAppShareMixin, TranslationAdmin)`.
- `portal/whatsapp.py`: add `Document` to the templates and `is_public`.
- `style.css`: list styling, following the Design section of `CLAUDE.md` (quiet, no card grid).
- Translations: new phrases into Tamil and Malay with `scripts/translations.py`.
- Backups: no change; `manage.py backup` already includes all of `media/`.

Not included: SVG and HTML uploads (they could run code in a visitor's browser), a separate file
per language, Google Drive links, and putting documents on the home page.

## Tests (`tests/test_documents.py`)

- Page groups documents in the fixed order, newest first, hides empty groups, shows the empty
  state, and shows the file type and size.
- Drafts and documents past their "remove after" date are not listed; a document whose date is
  today is still listed.
- Permanent link redirects for a published document, also past its date; 404 for drafts and
  unknown numbers.
- Wrong file type and files over 10 MB are refused with the messages above.
- Replacing a file deletes the old one; deleting a document deletes its file.
- WhatsApp button only for listed documents; message has title, note and permanent link.
- `setup_roles` gives Editors the document permissions.
- Add `/documents/` to the browser tests' page list.

## Going live

Push, then on PythonAnywhere: `git pull`, `migrate`, `setup_roles` (gives Editors the new
permissions), `collectstatic`, then Reload on the Web tab.
