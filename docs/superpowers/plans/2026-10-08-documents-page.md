# Documents Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public "Documents" page where staff publish circulars, forms, timetables and school documents, each with a permanent link and a "Share on WhatsApp" button in the admin.

**Architecture:** A new `Document` model (translated title and note, group, uploaded file, optional "remove after" date) in `portal/models.py`, following the existing content-type pattern (`published()` queryset, `TranslationAdmin`, `require_one_language`). Two public views: a grouped list and a permanent link that redirects to the current file. The admin reuses `WhatsAppShareMixin` and `portal/whatsapp.py`.

**Tech Stack:** Django 6.1, django-modeltranslation, pytest-django, Playwright browser tests, Babel-based `scripts/translations.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-documents-page-design.md`

## Global Constraints

- Allowed file types: pdf, doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png. Max 10 MB.
- Wrong type message: "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file."
- Too big message: "This file is {N} MB. The limit is 10 MB. Try saving the PDF at a smaller size." ({N} rounded up)
- Group order on the page: Circulars, Forms, Timetables and lists, School documents.
- A document with "remove after" = today is still listed; it leaves the page the next day (local time, `timezone.localdate()`).
- `/documents/<pk>/` redirects for any published document, even past its date; 404 for unpublished or unknown.
- Every user-facing string goes through `{% translate %}` / `gettext_lazy`; Tamil and Malay filled in, never left empty. Use `scripts/translations.py update` / `compile`, not makemessages.
- Design: follow `CLAUDE.md` Design (quiet list, no card grid, no all-caps, no arrows on links).
- Commands from the repo root: `.venv\Scripts\python -m pytest`, `.venv\Scripts\ruff check .`.
- Tests that create documents must point `MEDIA_ROOT` at `tmp_path` so they never write into the real `media/`.

## Review Focus

1. File names with spaces or Tamil letters (e.g. `சுற்றறிக்கை 1.pdf`) upload and open through the permanent link. Test in Task 2.
2. Upper-case extensions such as `FORM.PDF` are accepted. Test in Task 1.
3. Saving a document without choosing a new file (e.g. only changing the title) keeps the file on disk. Test in Task 1.
4. A document whose file is missing from disk (database restored without photos) doesn't crash the page; it shows without a size. Test in Task 2.
5. A document past its "remove after" date is not offered for sharing, and the admin says why. Test in Task 3.

---

### Task 1: Document model, validation and file clean-up

**Files:**
- Modify: `portal/models.py`
- Modify: `portal/translation.py`
- Create: `portal/migrations/0009_document.py` (generated)
- Test: `tests/test_documents.py`

**Interfaces:**
- Produces: `Document` with constants `CIRCULAR`, `FORM`, `LIST`, `SCHOOL`, `GROUPS` (list of `(key, lazy label)`), fields `title`, `note`, `group`, `file`, `remove_after`, `is_published`, `added_at`; `Document.objects.published()`; `get_absolute_url()` → `reverse("portal:document_open", args=[pk])` (route added in Task 2); properties `file_type -> str` and `file_size -> str` ("" if the file is missing).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_documents.py`:

```python
import math
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from portal.models import MAX_DOCUMENT_BYTES, Document


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def make_document(db):
    def _make(
        title="Booklist", group=Document.LIST, name="file.pdf", content=b"%PDF-1.4", **fields
    ):
        return Document.objects.create(
            title=title, group=group, file=SimpleUploadedFile(name, content), **fields
        )

    return _make


def unsaved(name, content=b"x", title="Booklist"):
    return Document(title=title, group=Document.LIST, file=SimpleUploadedFile(name, content))


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["page.html", "logo.svg", "run.exe", "notes.txt"])
def test_only_office_files_pdfs_and_photos_are_accepted(name):
    with pytest.raises(ValidationError) as error:
        unsaved(name).full_clean()
    assert error.value.message_dict["file"] == [
        "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["form.pdf", "FORM.PDF", "list.xlsx", "photo.JPG"])
def test_allowed_files_pass(name):
    unsaved(name).full_clean()


@pytest.mark.django_db
def test_files_over_10_mb_are_refused_with_their_size():
    document = unsaved("big.pdf", b"0" * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(ValidationError) as error:
        document.full_clean()
    size = math.ceil((MAX_DOCUMENT_BYTES + 1) / 1024 / 1024)
    assert error.value.message_dict["file"] == [
        f"This file is {size} MB. The limit is 10 MB. Try saving the PDF at a smaller size."
    ]


@pytest.mark.django_db
def test_title_is_needed_in_one_language():
    with pytest.raises(ValidationError) as error:
        unsaved("form.pdf", title="").full_clean()
    assert "title_ta" in error.value.message_dict


def test_published_hides_drafts_and_documents_past_their_date(make_document):
    today = timezone.localdate()
    make_document("Draft", is_published=False)
    make_document("Expired", remove_after=today - timedelta(days=1))
    make_document("Last day", remove_after=today)
    make_document("Kept")

    titles = {d.title for d in Document.objects.published()}

    assert titles == {"Last day", "Kept"}


def test_file_type_and_size(make_document):
    document = make_document(name="form.pdf", content=b"x" * 2048)
    assert document.file_type == "PDF"
    assert document.file_size == "2.0\xa0KB"
    assert make_document(name="list.XLSX").file_type == "Excel"


def test_replacing_the_file_deletes_the_old_one(make_document):
    document = make_document(name="old.pdf")
    old_path = Path(document.file.path)

    document.file = SimpleUploadedFile("new.pdf", b"%PDF new")
    document.save()

    assert not old_path.exists()
    assert Path(document.file.path).exists()


def test_saving_without_a_new_file_keeps_it(make_document):
    document = make_document()
    path = Path(document.file.path)

    document.refresh_from_db()
    document.title = "Booklist 2027"
    document.save()

    assert path.exists()


def test_deleting_a_document_deletes_its_file(make_document):
    document = make_document()
    path = Path(document.file.path)

    document.delete()

    assert not path.exists()
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `.venv\Scripts\python -m pytest tests/test_documents.py -q`
Expected: collection error, `ImportError: cannot import name 'MAX_DOCUMENT_BYTES'`.

- [ ] **Step 3: Add the model**

In `portal/models.py`, add to the imports:

```python
import math
from pathlib import PurePath

from django.core.validators import FileExtensionValidator, URLValidator
from django.db.models.signals import post_delete, post_save, pre_save
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _
```

(merge with the existing `URLValidator` and `post_delete` imports rather than duplicating them). Then append:

```python
DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "jpg", "jpeg", "png"]
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
FILE_TYPE_NAMES = {
    "pdf": "PDF",
    "doc": "Word",
    "docx": "Word",
    "xls": "Excel",
    "xlsx": "Excel",
    "ppt": "PowerPoint",
    "pptx": "PowerPoint",
    "jpg": "JPG",
    "jpeg": "JPG",
    "png": "PNG",
}


def validate_document_size(file) -> None:
    if file.size > MAX_DOCUMENT_BYTES:
        size = math.ceil(file.size / 1024 / 1024)
        raise ValidationError(
            f"This file is {size} MB. The limit is 10 MB. Try saving the PDF at a smaller size."
        )


class DocumentQuerySet(models.QuerySet):
    def published(self):
        """Published documents whose "remove after" day hasn't passed yet."""
        return self.filter(is_published=True).filter(
            Q(remove_after__isnull=True) | Q(remove_after__gte=timezone.localdate())
        )


class Document(models.Model):
    """A circular, form, timetable or other file for parents, on the Documents page."""

    CIRCULAR, FORM, LIST, SCHOOL = "circular", "form", "list", "school"
    # The order here is the order of the headings on the page.
    GROUPS = [
        (CIRCULAR, _("Circulars")),
        (FORM, _("Forms")),
        (LIST, _("Timetables and lists")),
        (SCHOOL, _("School documents")),
    ]

    title = models.CharField(max_length=200)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional, one line, e.g. “Return by Friday 17 October”.",
    )
    group = models.CharField(max_length=20, choices=GROUPS)
    file = models.FileField(
        upload_to="documents/%Y/",
        validators=[
            FileExtensionValidator(
                DOCUMENT_EXTENSIONS,
                message="Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file.",
            ),
            validate_document_size,
        ],
        help_text="PDF, Word, Excel, PowerPoint, JPG or PNG, up to 10 MB.",
    )
    remove_after = models.DateField(
        "remove after",
        null=True,
        blank=True,
        help_text="It leaves the Documents page after this day. Leave empty to keep it there.",
    )
    is_published = models.BooleanField("published", default=True)
    added_at = models.DateTimeField("added", auto_now_add=True)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-added_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portal:document_open", args=[self.pk])

    def clean(self) -> None:
        require_one_language(self, "title", "Give the document a title in at least one language.")

    @property
    def file_type(self) -> str:
        extension = PurePath(self.file.name).suffix.lstrip(".").lower()
        return FILE_TYPE_NAMES.get(extension, extension.upper())

    @property
    def file_size(self) -> str:
        try:
            return filesizeformat(self.file.size)
        except OSError:  # the file is missing, e.g. a database restored without media/
            return ""


@receiver(pre_save, sender=Document)
def _remember_old_document_file(sender, instance, **kwargs):
    instance._old_file = (
        sender.objects.filter(pk=instance.pk).values_list("file", flat=True).first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=Document)
def _delete_replaced_document_file(sender, instance, **kwargs):
    old = getattr(instance, "_old_file", None)
    if old and old != instance.file.name:
        instance.file.storage.delete(old)


@receiver(post_delete, sender=Document)
def _delete_document_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
```

In `portal/translation.py`, add `Document` to the models import and register:

```python
@register(Document)
class DocumentTranslation(AnyLanguage):
    fields = ("title", "note")
```

- [ ] **Step 4: Make the migration**

Run: `.venv\Scripts\python manage.py makemigrations portal`
Expected: `portal/migrations/0009_document.py` creating `Document` with `title_ta/ms/en`, `note_ta/ms/en`.

- [ ] **Step 5: Run the tests**

Run: `.venv\Scripts\python -m pytest tests/test_documents.py -q`
Expected: all pass. (`get_absolute_url` isn't called yet, so the missing route doesn't matter.)

- [ ] **Step 6: Commit**

```bash
git add portal/models.py portal/translation.py portal/migrations/0009_document.py tests/test_documents.py
git commit -m "Add Document model for the documents page"
```

---

### Task 2: Documents page, permanent link and menu

**Files:**
- Modify: `portal/views.py`, `portal/urls.py`, `portal/templates/portal/base.html`, `portal/static/portal/style.css`, `tests/test_browser.py`
- Create: `portal/templates/portal/document_list.html`
- Test: `tests/test_documents.py`
- Translations: `locale/ta|ms/LC_MESSAGES/django.po|mo`

**Interfaces:**
- Consumes: `Document`, `Document.GROUPS`, `Document.objects.published()`, `file_type`, `file_size` (Task 1).
- Produces: URL names `portal:document_list` (`/documents/`) and `portal:document_open` (`/documents/<pk>/`). Template context `groups`: list of `(label, [Document, ...])`, non-empty groups only, in `GROUPS` order.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_documents.py` (add `from django.urls import reverse` to the imports):

```python
def test_page_groups_documents_in_fixed_order_newest_first(make_document, client):
    make_document("Trip form", Document.FORM)
    old = make_document("Old circular", Document.CIRCULAR)
    Document.objects.filter(pk=old.pk).update(added_at=timezone.now() - timedelta(days=5))
    make_document("New circular", Document.CIRCULAR)

    groups = client.get(reverse("portal:document_list")).context["groups"]

    assert [str(label) for label, _ in groups] == ["Circulars", "Forms"]
    assert [d.title for d in groups[0][1]] == ["New circular", "Old circular"]


def test_page_shows_note_type_and_size_but_not_hidden_documents(make_document, client):
    make_document("Trip form", Document.FORM, note="Return by Friday", content=b"x" * 2048)
    make_document("Draft", is_published=False)
    make_document("Expired", remove_after=timezone.localdate() - timedelta(days=1))

    html = client.get(reverse("portal:document_list")).content.decode()

    assert "Trip form" in html
    assert "Return by Friday" in html
    assert "PDF, 2.0\xa0KB" in html
    assert "Draft" not in html
    assert "Expired" not in html


@pytest.mark.django_db
def test_page_without_documents_says_so(client):
    html = client.get(reverse("portal:document_list")).content.decode()
    assert "No documents yet." in html


def test_page_survives_a_missing_file(make_document, client):
    document = make_document("Lost file")
    Path(document.file.path).unlink()

    response = client.get(reverse("portal:document_list"))

    assert response.status_code == 200
    assert "Lost file" in response.content.decode()


def test_permanent_link_opens_the_file_even_after_its_date(make_document, client):
    document = make_document(remove_after=timezone.localdate() - timedelta(days=30))

    response = client.get(document.get_absolute_url())

    assert response.status_code == 302
    assert response["Location"] == document.file.url


def test_permanent_link_works_for_tamil_file_names(make_document, client):
    document = make_document(name="சுற்றறிக்கை 1.pdf")

    response = client.get(document.get_absolute_url())

    assert response.status_code == 302
    assert Path(document.file.path).exists()
    assert response["Location"] == document.file.url


def test_permanent_link_is_gone_for_drafts_and_unknown_numbers(make_document, client):
    draft = make_document(is_published=False)
    assert client.get(draft.get_absolute_url()).status_code == 404
    assert client.get(reverse("portal:document_open", args=[99999])).status_code == 404


@pytest.mark.django_db
def test_menu_links_to_documents(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert f'href="{reverse("portal:document_list")}"' in html
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `.venv\Scripts\python -m pytest tests/test_documents.py -q`
Expected: new tests fail with `NoReverseMatch: 'document_list' is not a valid view function or pattern name`.

- [ ] **Step 3: Add the views and routes**

In `portal/views.py`, add `Document` to the `.models` import and add:

```python
def document_list(request):
    documents = list(Document.objects.published())
    groups = [
        (label, [d for d in documents if d.group == key]) for key, label in Document.GROUPS
    ]
    return render(
        request,
        "portal/document_list.html",
        {"groups": [(label, docs) for label, docs in groups if docs]},
    )


def document_open(request, pk):
    """The permanent link for a document, used on the page and in WhatsApp messages.

    It keeps working after the "remove after" date so links in older messages still open.
    """
    document = get_object_or_404(Document.objects.filter(is_published=True), pk=pk)
    return redirect(document.file.url)
```

In `portal/urls.py`, after the gallery routes:

```python
    path("documents/", views.document_list, name="document_list"),
    path("documents/<int:pk>/", views.document_open, name="document_open"),
```

- [ ] **Step 4: Add the template**

Create `portal/templates/portal/document_list.html`:

```html
{% extends "portal/base.html" %}
{% load i18n %}

{% block title %}{% translate "Documents" %}, {{ school_name }}{% endblock %}

{% block content %}
<header class="page-head">
  <h1>{% translate "Documents" %}</h1>
  <p class="meta">{% translate "Circulars, forms and timetables from the school. Tap a title to open it." %}</p>
</header>

{% for label, documents in groups %}
  <section class="document-group" aria-labelledby="group-{{ forloop.counter }}">
    <h2 id="group-{{ forloop.counter }}">{{ label }}</h2>
    <ul class="document-list">
      {% for document in documents %}
        <li>
          <a href="{{ document.get_absolute_url }}">{{ document.title }}</a>
          {% if document.note %}<p>{{ document.note }}</p>{% endif %}
          <p class="meta"><time datetime="{{ document.added_at|date:'c' }}">{{ document.added_at|date:"j F Y" }}</time> · {{ document.file_type }}{% if document.file_size %}, {{ document.file_size }}{% endif %}</p>
        </li>
      {% endfor %}
    </ul>
  </section>
{% empty %}
  <p class="meta">{% translate "No documents yet." %}</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Add the menu links and styles**

In `portal/templates/portal/base.html`, after the Photos link in `.site-nav`:

```html
          <a href="{% url 'portal:document_list' %}"{% if "document" in current %} aria-current="page"{% endif %}>{% translate "Documents" %}</a>
```

and after the Photos link in `.footer-links`:

```html
        <a href="{% url 'portal:document_list' %}">{% translate "Documents" %}</a>
```

In `portal/static/portal/style.css`, after the `.calendar-subscribe` block:

```css
/* Documents */

.document-group { max-width: var(--measure); margin-top: 2rem; }
.document-group h2 { font-size: var(--step-1); }
.document-list { margin: 0; padding: 0; list-style: none; }
.document-list li { padding: 0.9rem 0; border-top: 1px solid var(--rule); }
.document-list li > a { font-weight: 600; }
.document-list p { margin: 0.2rem 0 0; }
```

In `tests/test_browser.py`, add `"/documents/",` to `page_paths` after the gallery entries (the page shows its empty state there, so no files are written).

- [ ] **Step 6: Translations**

Run `.venv\Scripts\python scripts/translations.py update`, then fill in:

| English | Tamil | Malay |
|---|---|---|
| Documents | ஆவணங்கள் | Dokumen |
| Circulars | சுற்றறிக்கைகள் | Surat edaran |
| Forms | படிவங்கள் | Borang |
| Timetables and lists | கால அட்டவணைகளும் பட்டியல்களும் | Jadual dan senarai |
| School documents | பள்ளி ஆவணங்கள் | Dokumen sekolah |
| Circulars, forms and timetables from the school. Tap a title to open it. | பள்ளியின் சுற்றறிக்கைகள், படிவங்கள், கால அட்டவணைகள். திறக்க தலைப்பைத் தொடுங்கள். | Surat edaran, borang dan jadual daripada sekolah. Sentuh tajuk untuk membukanya. |
| No documents yet. | இன்னும் ஆவணங்கள் இல்லை. | Belum ada dokumen. |

Then run `.venv\Scripts\python scripts/translations.py compile`.

- [ ] **Step 7: Run the tests**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass, including the browser tests and `test_languages.py` (no untranslated phrases).

- [ ] **Step 8: Commit**

```bash
git add portal/views.py portal/urls.py portal/templates/portal/document_list.html portal/templates/portal/base.html portal/static/portal/style.css tests/test_documents.py tests/test_browser.py locale
git commit -m "Add the Documents page and permanent document links"
```

---

### Task 3: Admin, WhatsApp sharing and Editors' permissions

**Files:**
- Modify: `portal/admin.py`, `portal/whatsapp.py`, `portal/management/commands/setup_roles.py`, `tests/test_whatsapp.py`
- Create: `portal/templates/portal/whatsapp/document.txt`
- Test: `tests/test_documents.py`
- Translations: `locale/...`

**Interfaces:**
- Consumes: `Document`, `Document.objects.published()`, `get_absolute_url()` (Tasks 1–2); `WhatsAppShareMixin`, `share_message`, `share_url`, `is_public` (existing).
- Produces: `DocumentAdmin`; `is_public(document)` true only for documents listed on the page.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_documents.py` (imports: `from django.contrib.auth.models import Group`, `from django.core.management import call_command`, `from portal.whatsapp import share_message`):

```python
def test_whatsapp_message_has_title_note_and_permanent_link(make_document, settings):
    settings.SITE_URL = "https://school.example"
    document = make_document("Zoo trip form", note="Return by Friday")

    text = share_message(document)

    assert text.startswith("*Zoo trip form*\nReturn by Friday\n")
    assert text.endswith(f"https://school.example/documents/{document.pk}/")


def test_admin_offers_sharing_only_for_listed_documents(make_document, admin_client):
    make_document("Booklist")
    expired = make_document("Old form", remove_after=timezone.localdate() - timedelta(days=1))

    html = admin_client.get(reverse("admin:portal_document_changelist")).content.decode()
    assert html.count("Share on WhatsApp") == 1

    url = reverse("admin:portal_document_change", args=[expired.pk])
    html = admin_client.get(url).content.decode()
    assert "Share on WhatsApp" not in html
    assert "Not shown to parents" in html


def test_admin_upload_refuses_wrong_file_type(admin_client):
    response = admin_client.post(
        reverse("admin:portal_document_add"),
        {
            "title_ta": "Form",
            "group": Document.FORM,
            "file": SimpleUploadedFile("page.html", b"<html>"),
            "is_published": "on",
        },
    )
    assert response.status_code == 200
    assert "Upload a PDF, Word, Excel, PowerPoint, JPG or PNG file." in response.content.decode()
    assert not Document.objects.exists()


@pytest.mark.django_db
def test_editors_can_manage_documents():
    call_command("setup_roles", stdout=None)
    codenames = set(
        Group.objects.get(name="Editors").permissions.values_list("codename", flat=True)
    )
    assert {"add_document", "change_document", "delete_document", "view_document"} <= codenames
```

In `tests/test_whatsapp.py`, change the two `"Not shown to parents yet"` assertions to `"Not shown to parents"` (the wording now also fits documents past their date).

- [ ] **Step 2: Run the tests to check they fail**

Run: `.venv\Scripts\python -m pytest tests/test_documents.py -q`
Expected: WhatsApp test fails with `KeyError: <class 'portal.models.Document'>`; admin tests fail with `NoReverseMatch`; editors test fails on missing codenames.

- [ ] **Step 3: WhatsApp message**

Create `portal/templates/portal/whatsapp/document.txt`:

```
{% load i18n %}{% autoescape off %}*{{ post.title }}*{% if post.note %}
{{ post.note }}{% endif %}

{% translate "Open the document:" %} {{ url }}
{% endautoescape %}
```

In `portal/whatsapp.py`, import `Document`, add `Document: "portal/whatsapp/document.txt"` to `TEMPLATES`, widen the type hints to `Event | Announcement | Document`, and add at the top of `is_public`:

```python
    if isinstance(obj, Document):
        return Document.objects.published().filter(pk=obj.pk).exists()
```

- [ ] **Step 4: Admin**

In `portal/admin.py`, import `Document`, change the mixin's not-public text to `"Not shown to parents right now, so it can't be shared."`, and add:

```python
@admin.register(Document)
class DocumentAdmin(WhatsAppShareMixin, TranslationAdmin):
    list_display = ["title", "group", "added_at", "remove_after", "is_published", "whatsapp_share"]
    list_editable = ["is_published"]
    list_filter = ["group", "is_published"]
    search_fields = in_all_languages("title", "note")
    readonly_fields = ["whatsapp_share"]
```

In `portal/management/commands/setup_roles.py`, add to `EDITOR_PERMISSIONS`:

```python
    "document": ["add", "change", "delete", "view"],
```

- [ ] **Step 5: Translations**

Run `scripts/translations.py update`; fill in "Open the document:" → Tamil `ஆவணத்தைத் திறக்க:`, Malay `Buka dokumen:`; run `compile`.

- [ ] **Step 6: Run everything**

Run: `.venv\Scripts\ruff check .` and `.venv\Scripts\python -m pytest -q`
Expected: no lint errors; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add portal/admin.py portal/whatsapp.py portal/templates/portal/whatsapp/document.txt portal/management/commands/setup_roles.py tests/test_documents.py tests/test_whatsapp.py locale
git commit -m "Manage and share documents in the admin"
```

---

### Task 4: Check it in the browser

- [ ] **Step 1:** Run the dev server, upload a PDF in the admin, and look at `/documents/` at phone width (390 px) and desktop width. Check the menu link, the grouping, the note line and that tapping the title opens the PDF.
- [ ] **Step 2:** Fix anything that looks off, re-run `pytest`, and commit.
