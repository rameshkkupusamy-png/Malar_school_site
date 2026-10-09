# Pupil achievements page: design

Date: 2026-10-09. Status: agreed in chat.

## Goal

Celebrate pupils' wins — competitions, certificates, team results — on the site, with names and
photos where parents agreed, without exposing children more than needed.

Decisions made with the school: names and photos (with a parents-agreed tick per pupil); newest
first by school year with category filters; a dedicated achievement entry with pupils and photos
listed under it (not news posts or free-text names).

## What parents see

- "Achievements" (Tamil சாதனைகள்) in the top menu and the footer.
- `/achievements/` shows one year at a time (`?year=YYYY`), defaulting to the latest year that has
  achievements, with links to the other years that have any. Year = the calendar year of the
  achievement's date.
- Filters: All, Academic, Sports, Arts and culture, Tamil language, Other (`?type=`). The filter
  is kept when switching years; years listed are those with achievements under the filter.
- Each entry: first photo (if photos are allowed), title, level label (School, District, State,
  National, International; State and above highlighted), date, and the pupils line.
- `/achievements/<pk>/`: all photos (if allowed), description, pupils.
- Empty: "No achievements yet."
- Both pages carry `<meta name="robots" content="noindex">`.

## Privacy rules

- Displayed name: given name(s) + initial. If the name contains a/l, a/p, s/o, d/o, bin, binti,
  bt or bte, the given names are the words before it and the initial is the first letter of the
  next word ("Kavin a/l Raju" → "Kavin R.", "Nur Aisyah binti Ahmad" → "Nur Aisyah A."). Otherwise
  first word + initial of the last word ("Meera Suresh" → "Meera S."; one word stays as is). The
  class follows in brackets: "Kavin R. (5 Mutiara)".
- "Show full name" per pupil shows the name as typed.
- A pupil without "parents agreed" is shown as "a Year 5 pupil" (first digit of the class) or
  "a pupil" — no name, no class.
- Photos appear only when every listed pupil has "parents agreed" (an achievement with no pupils
  listed may show photos). The admin says when photos are held back.
- Photos go through the existing upload shrinking (upright, ≤2000 px, no GPS).

## What staff do

Admin "Achievements": title and optional description (Tamil/Malay/English, title in at least one),
date (default today), category, level, published (default on). Inline pupils: name, class,
parents agreed, show full name. Inline photos: image, caption, order. List: title, date, category,
level, published, consent summary ("all agreed" / "2 of 3 agreed"), WhatsApp button. WhatsApp
message: title, the displayed pupils line, link. Editors manage achievements, pupils and photos.

## Tests

Name shortening (a/l, bin, plain, one word), year label, consent display, photo rule, photo
shrinking, years/filters/empty state, detail page, drafts hidden, noindex, menu link, admin with
inlines as an Editor, consent summary and held-back warning, WhatsApp text, translations, browser
tests at 360 px.
