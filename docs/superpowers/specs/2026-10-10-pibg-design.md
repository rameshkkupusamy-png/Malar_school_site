# PIBG page: design

Date: 2026-10-10. Status: agreed in chat.

## Goal

Give the Parent-Teacher Association (PIBG) one page that answers a new parent's questions: what is
PIBG, what do I pay, who is on the committee, when do they meet, and where are the minutes.

Decisions made in chat: the page covers the committee, meetings and the AGM, minutes and circulars,
and how to take part. Committee members are shown by name and role only; parents reach them through
one shared contact. Only the current committee is kept.

Success: after the AGM an editor updates the committee in a few minutes, and PIBG meetings and
documents appear on the page without being entered twice.

## What parents see

`/pibg/`, in this order; each part is hidden when it has nothing to show.

1. **Heading** "PIBG" with the line "Parent-Teacher Association" (Tamil: பெற்றோர் ஆசிரியர் சங்கம்;
   Malay: Persatuan Ibu Bapa dan Guru).
2. **About and how to take part**: the editable `about` text (line breaks kept), then the shared
   contact: phone (`tel:` link), email (`mailto:` link), WhatsApp group (link). Each is optional.
3. **Upcoming meetings**: published PIBG events (`kind="pibg"`) from `Event.objects.published()
   .upcoming()`, soonest first, rendered with `_event_row.html`, followed by a link "All PIBG
   events" to `/events/?type=pibg`.
4. **Committee for {term}**: a plain list (not cards) of role and name. Order: role order below,
   then `order`, then name. Heading reads "Committee" when no term is set.
5. **Minutes and circulars**: `Document.objects.published()` in the PIBG group, newest first,
   same row format as the Documents page.
6. **Past meetings**: the 5 most recent past PIBG events from `.past()`, newest first.

- If every part is empty: "Details coming soon."
- `<meta name="robots" content="noindex">` on the page.
- "PIBG" in the top menu after Documents, and in the footer; `aria-current="page"` on `/pibg/`.
- The Documents page gains a "PIBG" heading listing the same documents.

Committee roles, in display order: Chairperson, Vice-chairperson, Secretary, Assistant secretary,
Treasurer, Assistant treasurer, Auditor, Advisor, Committee member. Two people may share a role.
Teachers (the headmaster as advisor, teacher representatives) use the same list.

## Data

- `Pibg` (one record, `pk` always 1, `load()` like `SchoolContact`):
  - `term` CharField(20, blank), e.g. "2026/2027".
  - `about` TextField(blank), translated (`about_ta/_ms/_en`) via modeltranslation.
  - `phone` CharField(30, blank, `validate_malaysian_number`), `phone_link` property.
  - `email` EmailField(blank), `email_link` property.
  - `whatsapp_group` URLField(blank, https only), help text "The PIBG WhatsApp group invite link".
  - `has_contact` property.
- `CommitteeMember`: `pibg` FK (related_name `committee`), `name` CharField(100), `role`
  CharField with the choices above, `order` PositiveSmallIntegerField(default 0). Names are not
  translated. Meta ordering by role rank is done in Python (role list index), then `order`, `name`.
- `Document.GROUPS` gains `(PIBG, _("PIBG"))`, placed before "School documents". Choices-only
  migration; existing rows unchanged.

## Admin

- `PibgAdmin` follows `SchoolContactAdmin`: no add once the record exists (redirect to change
  page), no delete, "Save and add another" not offered.
- `CommitteeMember` is a tabular inline on `PibgAdmin` with fields name, role, order and the help
  text "Shown publicly. Add only people who agreed to be listed."
- `setup_roles`: Editors get `change_pibg`, `view_pibg`, and add/change/delete/view on
  `committeemember`. (`add_pibg` too, so an editor can create the record the first time.)

## Privacy

- Committee names appear only on `/pibg/`; they are not added to site search, and the page is
  `noindex`.
- No personal phone numbers; only the shared PIBG contact is shown.

## Translations

All new strings (page wording, role names, "PIBG" group label) wrapped in `gettext` /
`{% translate %}`, then `scripts/translations.py update`, Tamil and Malay filled in, `compile`.
"PIBG" itself stays "PIBG" in every language.

## Tests (`tests/test_pibg.py`)

- Each part shows only with content; an empty setup shows "Details coming soon."
- Committee ordered by role list, then `order`; two people in one role both shown.
- Upcoming meetings: only published, future PIBG events; other kinds never appear. Past meetings: at
  most 5, newest first.
- PIBG documents: only published, unexpired documents in the PIBG group; Documents page shows the
  PIBG heading.
- Page has `noindex`; menu link with `aria-current`; `find()` with a committee member's name returns
  nothing.
- Shared contact: links built only for filled fields; an invalid phone or non-https link is refused
  by validation.
- Admin: the record can't be added twice or deleted; an Editors member (after `setup_roles`) can
  open the PIBG change page and add a committee member.
- Browser sweep (`tests/test_browser.py`): `/pibg/` in all three languages at phone and desktop
  width with no sideways scroll, with the seven-item menu.

## Out of scope

Past committees, member photos or personal contacts, online fee payment, meeting attendance or RSVP.
