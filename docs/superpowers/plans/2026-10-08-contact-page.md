# Contact Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/contact/` page with call, WhatsApp, email and directions buttons, from one staff-editable "Contact details" record.

**Architecture:** A single-row `SchoolContact` model (translated `hours`) with link-building properties, a plain view and template, and an admin that only ever edits the one record. Malaysian phone numbers are normalised by one helper used by the validator and the links.

**Tech Stack:** Django 6.1, django-modeltranslation, pytest-django, Playwright, `scripts/translations.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-contact-page-design.md`

## Global Constraints

- Phone rule: ignore spaces, `-`, `.`, `(`, `)`; accept leading `0`, `60` or `+60`; the national part is 8–10 digits and doesn't start with 0. Error: "Enter a Malaysian phone number, for example 03-8723 1234 or 012-345 6789."
- Section order: Phone, WhatsApp, Email, Visit us. Empty sections are hidden; nothing at all → "Contact details will be added soon."
- No embedded map.
- Every user-facing string translated into Tamil and Malay (never empty); use `scripts/translations.py`, not makemessages.
- Tests run with `.venv\Scripts\python -m pytest`; lint `ruff check .` and `ruff format --check .`.

## Review Focus

1. Numbers with odd spacing or a `+60` prefix (`+60 12-345 6789`, `(03) 8723-1234`) produce the same links as the plain form. Test in Task 1.
2. An address with commas, `#` or `&` (e.g. "Lot 123, Jalan A & B") is escaped in the map links. Test in Task 1.
3. A Google Maps link pasted with `javascript:` is refused. Test in Task 1.
4. The admin list page for contact details never shows an empty list or an "Add" button once the record exists. Test in Task 3.
5. Saving the contact record twice (or from two tabs) never creates a second row. Test in Task 1.

---

### Task 1: Phone numbers and the contact record

**Files:** Modify `portal/models.py`, `portal/translation.py`; create `portal/migrations/0010_schoolcontact.py` (generated); test `tests/test_contact.py`.

**Interfaces — Produces:** `malaysian_number(value: str) -> str` (raises `ValueError`); `validate_malaysian_number(value)`; `SchoolContact` fields `phone`, `whatsapp`, `email`, `address`, `hours`, `map_url`; `SchoolContact.load() -> SchoolContact` (saved row or unsaved blank); properties `phone_link`, `whatsapp_link`, `email_link`, `google_maps_link`, `waze_link` (each `""` when not applicable), `can_visit: bool`, `has_details: bool`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_contact.py`:

```python
import pytest
from django.core.exceptions import ValidationError

from portal.models import SchoolContact, malaysian_number


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("03-8723 1234", "60387231234"),
        ("(03) 8723-1234", "60387231234"),
        ("012-345 6789", "60123456789"),
        ("+60 12-345 6789", "60123456789"),
        ("60123456789", "60123456789"),
        ("011-1234 5678", "601112345678"),
        ("06-123 4567", "6061234567"),
    ],
)
def test_malaysian_numbers_in_common_forms(typed, expected):
    assert malaysian_number(typed) == expected


@pytest.mark.parametrize("typed", ["12345", "+65 9123 4567", "03-8723 12345678", "phone", "600123456"])
def test_other_numbers_are_refused(typed):
    with pytest.raises(ValueError):
        malaysian_number(typed)


@pytest.mark.django_db
def test_bad_number_gets_a_clear_message():
    with pytest.raises(ValidationError) as error:
        SchoolContact(phone="12345").full_clean()
    assert error.value.message_dict["phone"] == [
        "Enter a Malaysian phone number, for example 03-8723 1234 or 012-345 6789."
    ]


@pytest.mark.django_db
def test_map_link_must_be_a_web_address():
    with pytest.raises(ValidationError) as error:
        SchoolContact(map_url="javascript:alert(1)").full_clean()
    assert "map_url" in error.value.message_dict


def test_links():
    contact = SchoolContact(
        phone="03-8723 1234",
        whatsapp="012-345 6789",
        email="office@school.example",
        address="Lot 123, Jalan A & B #2, Semenyih",
    )
    assert contact.phone_link == "tel:+60387231234"
    assert contact.whatsapp_link == "https://wa.me/60123456789"
    assert contact.email_link == "mailto:office@school.example"
    query = "Lot%20123%2C%20Jalan%20A%20%26%20B%20%232%2C%20Semenyih"
    assert contact.google_maps_link == (
        f"https://www.google.com/maps/search/?api=1&query={query}"
    )
    assert contact.waze_link == f"https://waze.com/ul?q={query}&navigate=yes"
    assert contact.can_visit and contact.has_details


def test_pasted_maps_link_wins_and_empty_record_has_nothing():
    assert SchoolContact(map_url="https://maps.app.goo.gl/abc").google_maps_link == (
        "https://maps.app.goo.gl/abc"
    )
    assert SchoolContact(map_url="https://maps.app.goo.gl/abc").waze_link == ""
    empty = SchoolContact()
    assert (empty.phone_link, empty.whatsapp_link, empty.google_maps_link) == ("", "", "")
    assert not empty.can_visit and not empty.has_details


@pytest.mark.django_db
def test_there_is_only_ever_one_record():
    assert SchoolContact.load().pk is None
    SchoolContact(email="a@school.example").save()
    SchoolContact(email="b@school.example").save()
    assert SchoolContact.objects.count() == 1
    assert SchoolContact.load().email == "b@school.example"
```

- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_contact.py -q`. Expected: `ImportError: cannot import name 'SchoolContact'`.

- [ ] **Step 3: Implement** — in `portal/models.py` add `import re` and `from urllib.parse import quote` to the imports, and append:

```python
PHONE_HELP = "Enter a Malaysian phone number, for example 03-8723 1234 or 012-345 6789."


def malaysian_number(value: str) -> str:
    """'03-8723 1234' -> '60387231234', the international form links need."""
    digits = re.sub(r"[\s\-.()]", "", value).removeprefix("+")
    if not digits.isdigit():
        raise ValueError(value)
    if digits.startswith("0"):
        digits = "60" + digits[1:]
    if not digits.startswith("60"):
        raise ValueError(value)
    national = digits[2:]
    if not 8 <= len(national) <= 10 or national.startswith("0"):
        raise ValueError(value)
    return digits


def validate_malaysian_number(value: str) -> None:
    try:
        malaysian_number(value)
    except ValueError:
        raise ValidationError(PHONE_HELP) from None


class SchoolContact(models.Model):
    """How parents reach the office. There is only ever one of these."""

    phone = models.CharField(
        max_length=30, blank=True, validators=[validate_malaysian_number], help_text="e.g. 03-8723 1234"
    )
    whatsapp = models.CharField(
        "WhatsApp number",
        max_length=30,
        blank=True,
        validators=[validate_malaysian_number],
        help_text="The office's WhatsApp number, e.g. 012-345 6789.",
    )
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, help_text="The postal address, as on a letter.")
    hours = models.TextField(
        "office hours", blank=True, help_text="e.g. Monday to Friday, 7.30 am to 1.00 pm"
    )
    map_url = models.URLField(
        "Google Maps link",
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Optional. Paste the school's Google Maps link so the button opens the exact pin.",
    )

    class Meta:
        verbose_name = verbose_name_plural = "contact details"

    def __str__(self) -> str:
        return "Contact details"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1  # one record, however it is saved
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SchoolContact":
        return cls.objects.first() or cls()

    @property
    def phone_link(self) -> str:
        return f"tel:+{malaysian_number(self.phone)}" if self.phone else ""

    @property
    def whatsapp_link(self) -> str:
        return f"https://wa.me/{malaysian_number(self.whatsapp)}" if self.whatsapp else ""

    @property
    def email_link(self) -> str:
        return f"mailto:{self.email}" if self.email else ""

    @property
    def google_maps_link(self) -> str:
        if self.map_url:
            return self.map_url
        if self.address:
            return f"https://www.google.com/maps/search/?api=1&query={quote(self._one_line_address)}"
        return ""

    @property
    def waze_link(self) -> str:
        if not self.address:
            return ""
        return f"https://waze.com/ul?q={quote(self._one_line_address)}&navigate=yes"

    @property
    def _one_line_address(self) -> str:
        return ", ".join(line.strip() for line in self.address.splitlines() if line.strip())

    @property
    def can_visit(self) -> bool:
        return bool(self.address or self.hours or self.map_url)

    @property
    def has_details(self) -> bool:
        return bool(self.phone or self.whatsapp or self.email or self.can_visit)
```

`quote(..., safe="")` is not needed: `quote`'s default keeps `/`, which is harmless in a query value; `,`, `&`, `#` and spaces are escaped as the test expects. In `portal/translation.py` import `SchoolContact` and register `fields = ("hours",)` with `AnyLanguage`. Run `.venv\Scripts\python manage.py makemigrations portal -n schoolcontact`.

- [ ] **Step 4: Run** the tests. Expected: all pass.
- [ ] **Step 5: Commit** "Add the school contact details record".

---

### Task 2: The contact page and footer link

**Files:** Modify `portal/views.py`, `portal/urls.py`, `portal/templates/portal/base.html`, `portal/static/portal/style.css`, `tests/test_browser.py`; create `portal/templates/portal/contact.html`; translations.

**Interfaces — Consumes:** `SchoolContact.load()` and its properties. **Produces:** URL `portal:contact`.

- [ ] **Step 1: Failing tests** — append to `tests/test_contact.py` (import `reverse`):

```python
@pytest.mark.django_db
def test_page_shows_only_what_is_filled_in(client):
    SchoolContact(phone="03-8723 1234", email="office@school.example").save()

    html = client.get(reverse("portal:contact")).content.decode()

    assert 'href="tel:+60387231234"' in html and "Call the office" in html
    assert 'href="mailto:office@school.example"' in html
    assert "Message the office on WhatsApp" not in html
    assert "Open in Waze" not in html


@pytest.mark.django_db
def test_page_with_address_offers_directions_and_hours(client):
    SchoolContact(address="Jalan Semenyih,\n43500 Semenyih", hours_en="Mon–Fri 7.30–1.00").save()

    html = client.get(reverse("portal:contact")).content.decode()

    assert "Open in Google Maps" in html and "Open in Waze" in html
    assert "43500 Semenyih" in html
    assert "Mon–Fri 7.30–1.00" in html


@pytest.mark.django_db
def test_page_without_details_says_so(client):
    html = client.get(reverse("portal:contact")).content.decode()
    assert "Contact details will be added soon." in html


@pytest.mark.django_db
def test_footer_links_to_contact_page(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert f'href="{reverse("portal:contact")}"' in html
```

- [ ] **Step 2: Run** — Expected: `NoReverseMatch` for `contact`.
- [ ] **Step 3: Implement**
  - `portal/views.py`: import `SchoolContact`; add
    ```python
    def contact(request):
        return render(request, "portal/contact.html", {"contact": SchoolContact.load()})
    ```
  - `portal/urls.py`: `path("contact/", views.contact, name="contact"),` after the documents routes.
  - `portal/templates/portal/contact.html`:
    ```html
    {% extends "portal/base.html" %}
    {% load i18n %}

    {% block title %}{% translate "Contact the school" %}, {{ school_name }}{% endblock %}

    {% block content %}
    <header class="page-head">
      <h1>{% translate "Contact the school" %}</h1>
    </header>

    {% if contact.has_details %}
      <div class="contact">
        {% if contact.phone %}
          <section aria-labelledby="contact-phone">
            <h2 id="contact-phone">{% translate "Phone" %}</h2>
            <p>{{ contact.phone }}</p>
            <p><a class="button" href="{{ contact.phone_link }}">{% translate "Call the office" %}</a></p>
          </section>
        {% endif %}
        {% if contact.whatsapp %}
          <section aria-labelledby="contact-whatsapp">
            <h2 id="contact-whatsapp">WhatsApp</h2>
            <p><a class="button" href="{{ contact.whatsapp_link }}" target="_blank" rel="noopener">{% translate "Message the office on WhatsApp" %}</a></p>
          </section>
        {% endif %}
        {% if contact.email %}
          <section aria-labelledby="contact-email">
            <h2 id="contact-email">{% translate "Email" %}</h2>
            <p>{{ contact.email }}</p>
            <p><a class="button" href="{{ contact.email_link }}">{% translate "Email the office" %}</a></p>
          </section>
        {% endif %}
        {% if contact.can_visit %}
          <section aria-labelledby="contact-visit">
            <h2 id="contact-visit">{% translate "Visit us" %}</h2>
            {% if contact.address %}<address>{{ contact.address|linebreaksbr }}</address>{% endif %}
            {% if contact.hours %}<h3>{% translate "Office hours" %}</h3><p>{{ contact.hours|linebreaksbr }}</p>{% endif %}
            {% if contact.google_maps_link or contact.waze_link %}
              <p class="button-row">
                {% if contact.google_maps_link %}<a class="button" href="{{ contact.google_maps_link }}" target="_blank" rel="noopener">{% translate "Open in Google Maps" %}</a>{% endif %}
                {% if contact.waze_link %}<a class="button button--quiet" href="{{ contact.waze_link }}" target="_blank" rel="noopener">{% translate "Open in Waze" %}</a>{% endif %}
              </p>
            {% endif %}
          </section>
        {% endif %}
      </div>
    {% else %}
      <p class="meta">{% translate "Contact details will be added soon." %}</p>
    {% endif %}
    {% endblock %}
    ```
  - `base.html` footer, after Documents: `<a href="{% url 'portal:contact' %}">{% translate "Contact the school" %}</a>`
  - `style.css`, after the Documents block:
    ```css
    /* Contact */

    .contact { max-width: var(--measure); }
    .contact section { padding-block: 1.25rem; border-top: 1px solid var(--rule); }
    .contact h2 { font-size: var(--step-1); }
    .contact h3 { margin: 1rem 0 0.25rem; font-size: var(--step-0); }
    .contact address { font-style: normal; }
    ```
  - `tests/test_browser.py`: add `"/contact/",` to `page_paths` after `"/documents/"`.
  - Translations (`update`, fill, `compile`):

    | English | Tamil | Malay |
    |---|---|---|
    | Contact the school | பள்ளியைத் தொடர்புகொள்ள | Hubungi sekolah |
    | Phone | தொலைபேசி | Telefon |
    | Call the office | அலுவலகத்தை அழைக்கவும் | Telefon pejabat |
    | Message the office on WhatsApp | அலுவலகத்துக்கு WhatsApp-இல் செய்தி அனுப்பவும் | Hantar mesej WhatsApp kepada pejabat |
    | Email | மின்னஞ்சல் | E-mel |
    | Email the office | அலுவலகத்துக்கு மின்னஞ்சல் அனுப்பவும் | E-mel pejabat |
    | Visit us | நேரில் வர | Kunjungi kami |
    | Office hours | அலுவலக நேரம் | Waktu pejabat |
    | Open in Google Maps | Google Maps-இல் திறக்கவும் | Buka di Google Maps |
    | Open in Waze | Waze-இல் திறக்கவும் | Buka di Waze |
    | Contact details will be added soon. | தொடர்பு விவரங்கள் விரைவில் சேர்க்கப்படும். | Butiran hubungan akan ditambah tidak lama lagi. |

- [ ] **Step 4: Run** the full suite (browser tests and `test_every_phrase_has_a_translation` included). Expected: all pass.
- [ ] **Step 5: Commit** "Add the contact page".

---

### Task 3: One record in the admin, Editors' access

**Files:** Modify `portal/admin.py`, `portal/management/commands/setup_roles.py`; test `tests/test_contact.py`.

**Interfaces — Consumes:** `SchoolContact`, `AnyLanguageAdmin` (existing).

- [ ] **Step 1: Failing tests** — append (imports: `Group`, `call_command`):

```python
@pytest.mark.django_db
def test_admin_list_opens_the_form_then_the_record(admin_client):
    url = reverse("admin:portal_schoolcontact_changelist")
    assert admin_client.get(url)["Location"] == reverse("admin:portal_schoolcontact_add")

    SchoolContact(email="office@school.example").save()
    assert admin_client.get(url)["Location"] == reverse(
        "admin:portal_schoolcontact_change", args=[1]
    )
    assert admin_client.get(reverse("admin:portal_schoolcontact_add")).status_code == 403


@pytest.mark.django_db
def test_admin_saves_details_and_refuses_bad_numbers(admin_client):
    url = reverse("admin:portal_schoolcontact_add")
    response = admin_client.post(url, {"phone": "12345"})
    assert "Enter a Malaysian phone number" in response.content.decode()

    admin_client.post(url, {"phone": "03-8723 1234", "hours_ms": "Isnin–Jumaat"})
    assert SchoolContact.load().phone_link == "tel:+60387231234"


@pytest.mark.django_db
def test_contact_details_cannot_be_deleted(admin_client):
    SchoolContact(email="office@school.example").save()
    url = reverse("admin:portal_schoolcontact_delete", args=[1])
    assert admin_client.get(url).status_code == 403


@pytest.mark.django_db
def test_editors_can_edit_contact_details():
    call_command("setup_roles", stdout=None)
    codenames = set(
        Group.objects.get(name="Editors").permissions.values_list("codename", flat=True)
    )
    assert {"add_schoolcontact", "change_schoolcontact", "view_schoolcontact"} <= codenames
```

- [ ] **Step 2: Run** — Expected: `NoReverseMatch` for the admin URLs; missing codenames.
- [ ] **Step 3: Implement** — in `portal/admin.py` import `SchoolContact` and `redirect` (already imported), and add:

```python
@admin.register(SchoolContact)
class SchoolContactAdmin(AnyLanguageAdmin):
    """The one contact record: the list page goes straight to it."""

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not SchoolContact.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if SchoolContact.objects.exists():
            return redirect("admin:portal_schoolcontact_change", 1)
        return redirect("admin:portal_schoolcontact_add")
```

In `setup_roles.py` add `"schoolcontact": ["add", "change", "view"],`.

- [ ] **Step 4: Run** the full suite and `ruff check .` / `ruff format --check .`. Expected: all pass.
- [ ] **Step 5: Commit** "Edit contact details in the admin".

---

### Task 4: Check it in the browser

- [ ] Fill in sample details in the local database, look at `/contact/` at 390 px and 1280 px, check every button's link, then delete the sample record from the database shell. Commit any CSS fix.
