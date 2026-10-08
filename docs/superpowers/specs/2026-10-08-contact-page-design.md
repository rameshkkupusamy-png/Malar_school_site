# Contact page: design

Date: 2026-10-08. Status: agreed in chat.

## Goal

Parents can reach the school office from the site in the way that suits them: call, WhatsApp,
email, or visit with directions. Staff keep the details up to date in the admin without a
developer.

Decisions made with the school: the office answers phone, WhatsApp and email, and parents visit
in person, so all four are offered. Details are edited by staff in the admin.

## What parents see

`/contact/`, titled "Contact the school", linked from the footer of every page (not the top
menu, which is already full on phones in Tamil). Only filled-in details appear, in this order:

1. **Phone**: the number as staff typed it, and a "Call the office" button (`tel:+60…`).
2. **WhatsApp**: a "Message the office on WhatsApp" button (`https://wa.me/60…`).
3. **Email**: the address, and an "Email the office" button (`mailto:`).
4. **Visit us**: the address, the office hours, and "Open in Google Maps" and "Open in Waze"
   buttons. No embedded map (slow on mobile data; sends visitor data to Google unasked).

With nothing filled in: "Contact details will be added soon."

## What staff do

One "Contact details" record in the admin. The list page goes straight to it; staff can't add
a second one or delete it.

| Field | Notes |
|---|---|
| Phone | Optional. Malaysian number in any common form |
| WhatsApp number | Optional. Same rules |
| Email | Optional |
| Address | Optional. One version (postal addresses are written once, usually in Malay) |
| Office hours | Optional. Tamil, Malay and/or English |
| Google Maps link | Optional, `http(s)` only. If set, "Open in Google Maps" opens it |

Phone numbers: spaces, dashes, dots and brackets are ignored; a leading `0`, `60` or `+60` is
accepted; the part after the country code must be 8–10 digits and not start with 0. Anything
else is refused with "Enter a Malaysian phone number, for example 03-8723 1234 or
012-345 6789." Links use the international form `60…`.

Map buttons: Google Maps uses the pasted link, else
`https://www.google.com/maps/search/?api=1&query=<address>`. Waze always uses
`https://waze.com/ul?q=<address>&navigate=yes`. Both appear only when there is an address or a
Maps link (Waze only with an address).

Editors (`setup_roles`) get add, change and view on contact details.

## Building blocks

- `portal/models.py`: `malaysian_number()` / `validate_malaysian_number()`, `SchoolContact` with
  `load()` and link properties.
- `portal/translation.py`: `hours`. Migration `0010`.
- `portal/views.py` `contact`, `portal/urls.py` `/contact/`, template `contact.html`, footer link,
  small CSS.
- `portal/admin.py`: `SchoolContactAdmin(AnyLanguageAdmin)` as a single record.
- Translations for every new phrase.

## Tests

Number formats and refusals; links from the record; the page showing only filled sections and
the empty message; footer link; single record in the admin; Editors' permissions; `/contact/`
in the browser tests.

## Going live

`git pull`, `migrate`, `setup_roles`, `collectstatic`, Reload. Then fill in the details in the
admin.
