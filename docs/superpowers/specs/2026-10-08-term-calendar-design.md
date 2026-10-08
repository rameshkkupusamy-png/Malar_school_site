# Term calendar: design

Date: 2026-10-08. Status: agreed in chat.

## Goal

Parents see the school year month by month — holidays, exam weeks, PIBG meetings, sports and
celebrations — on the Events page, from the events staff already publish.

Decisions made with the school: one calendar built from events (no separate term-dates list);
a month-by-month list, not a grid; it replaces the Upcoming / Past tabs.

## What parents see (`/events/`)

- Opens on the current month (school time zone): heading "October 2026" (localised), with
  "Previous month" and "Next month" links. `?month=YYYY-MM` picks a month; anything else (bad
  value, old `?show=past` links) shows the current month.
- Filters above the list: All, Holidays, Exams, PIBG, Sports, Celebrations (`?type=…`). The
  filter is kept when moving between months. An unknown type shows All.
- The month lists every published event that overlaps it (starts before the month ends and ends,
  or starts if it has no end, on or after the month starts), oldest first, in the existing row
  style. An event spanning two months appears in both with its full dates.
- Markers: holidays get a soft yellow band (torch yellow, tinted) and a "Holiday" label; exams a
  blue "Exam" label; PIBG, Sports and Celebration a quiet muted label; plain events none. The same
  labels show wherever event rows appear (home page too).
- Empty month: "No events this month." plus, if a later month has events (with the current
  filter), a link "Next: December 2026" to it.
- The calendar subscription box stays at the bottom.

## What staff do

- `Event.kind`: Event (default), Holiday, Exam, PIBG, Sports, Celebration. Existing events become
  Event. Admin: shown in the list and filterable.
- Spreadsheet import: optional "Type" column. Recognised words (any case): 
  Holiday — holiday, holidays, cuti, விடுமுறை; Exam — exam, exams, examination, test,
  peperiksaan, ujian, தேர்வு, பரீட்சை; PIBG — pibg, pta, பெற்றோர் ஆசிரியர் சங்கம்;
  Sports — sports, sport, sukan, விளையாட்டு; Celebration — celebration, perayaan, sambutan,
  கொண்டாட்டம், விழா; Event — event, acara, நிகழ்வு, or empty. Anything else becomes Event, and the
  review page lists a note: "Row N (title): the type 'x' wasn't recognised, so it was saved as
  Event."
- The review page has a Type column so staff can change it before publishing.
- The template gets the Type column, its instructions, and types in the examples.

## Unchanged

Home page "next event", event pages, "Add to my calendar", the calendar feed, WhatsApp sharing,
emails.

## Tests

Months and overlap (including events spanning months and without an end), current-month default
and bad/old parameters, previous/next links keeping the filter, filters, empty month with and
without a later month, type labels and holiday band, admin filter, import Type column in three
languages plus unknown words, review-page type change, translations, browser tests with a
filter URL.
