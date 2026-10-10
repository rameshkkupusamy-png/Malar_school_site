# Site search: design

Date: 2026-10-10. Status: agreed in chat.

## Goal

Let parents find something they half-remember ("sports day", "booklist", "cuti") with one search
box, whatever language the post was written in.

Decisions made in chat: search events, news, documents, achievements and albums; reach it from a
"Search" link in the header that opens its own page; plain database matching, no search index or
outside service; pupil names are never searchable.

Success: a parent types a word in Tamil, Malay or English and finds the post that contains it,
whichever language column that word is stored in.

## What parents see

- "Search" in the top menu (after Achievements) and in the footer. The link has
  `aria-current="page"` on the search page.
- `/search/?q=…` shows the heading "Search the school site", one labelled `type="search"` box
  (filled with the current query) and a "Search" button.
- No query, or a query under 2 characters after trimming: only the box and the hint "Type a word
  from the title, for example sports day or booklist."
- Results are grouped in this fixed order: Events, News, Documents, Achievements, Photos. Each
  section heading shows its count, e.g. "Events (3)". Sections with no matches are hidden.
- Each section lists at most 10 items as a plain list (not cards): a title link in the visitor's
  language (usual modeltranslation fallback) plus a date or type line. Events reuse
  `_event_row.html` so dates match the Events page.
- If a section has more than 10 matches it ends with "Showing the first 10 of N. Try a more
  specific word." No paging.
- Nothing found anywhere: "Nothing matched. Try another word." followed by the existing "Contact the
  school" link to the contact page.
- The page carries `<meta name="robots" content="noindex">`.

## Matching rules

- The query is trimmed and cut to 100 characters, then split on whitespace; only the first 5
  words are used.
- An item matches when **every** word appears (substring, `icontains`) in at least one of its
  searched fields in any of the three language columns (`_ta`, `_ms`, `_en`). Case is ignored for
  Latin letters (SQLite `LIKE`); Tamil has no case and matches as typed.
- Searched fields and the queryset each section starts from:

  | Section      | Starts from                                   | Fields                            | Order                                         |
  |--------------|-----------------------------------------------|-----------------------------------|-----------------------------------------------|
  | Events       | `Event.objects.published()`                   | title, description, location      | upcoming first (soonest), then past newest first |
  | News         | `Announcement.objects.published()`            | title, body                       | newest `published_at` first                   |
  | Documents    | `Document.objects.published()`                | title, note                       | newest `added_at` first                       |
  | Achievements | `Achievement.objects.published()`             | title, description                | newest `date` first                           |
  | Photos       | `Album.objects.filter(is_published=True)`     | title, description                | newest `created_at` first                     |

- Starting from the published querysets means unpublished, scheduled (future `published_at`) and
  expired ("remove after" passed) content is excluded before matching.
- Pupil records (`AchievementPupil`), photo captions and file contents are not searched.

## Code

- `portal/search.py`: `find(query: str) -> list[Section]`, where a section holds its key,
  heading, total count and first 10 items. A helper builds, per word, an OR of `icontains` across
  `field_ta / field_ms / field_en` for the section's fields, and ANDs the words together. Returns
  an empty list for queries under 2 characters.
- `portal/views.py`: `search` view reads `q`, calls `find()`, renders `portal/search.html`.
- `portal/urls.py`: `path("search/", views.search, name="search")`.
- `portal/templates/portal/search.html` extends `base.html`; header and footer links added in
  `base.html`. Styles in `style.css` using the existing tokens (blue links, rule lines between
  items, yellow focus ring on the box).
- New strings wrapped in `{% translate %}` / `gettext`, then `scripts/translations.py update`,
  Tamil and Malay entries filled in, `compile`.
- No model changes, no migrations, no new dependencies.

## Tests (`tests/test_search.py`)

- Finds an event by a word stored only in `title_ta`, only in `title_ms`, only in `title_en`.
- Finds by description/body/note/location, not just title.
- Two-word query requires both words; English matching ignores case.
- Excludes unpublished items of every type, news with a future `published_at`, and documents past
  "remove after".
- A pupil's name that appears only in an `AchievementPupil` record returns no result.
- Empty and 1-character queries show the hint and no sections; a 500-character query renders.
- More than 10 matches shows 10 items and the "first 10 of N" line.
- Page has `noindex`; header link present with `aria-current` on the search page.
- Browser test (`tests/test_browser.py`): at phone width the menu wraps cleanly, searching and
  clicking a result opens it.

## Out of scope

Relevance ranking, stemming, searching inside PDFs, search-as-you-type, paging, a search box in
the header.
