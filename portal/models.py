import math
import re
import unicodedata
import uuid
from datetime import date, datetime, time
from pathlib import PurePath
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator, URLValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .images import shrink_new_upload

LANGUAGE_CODES = ("ta", "ms", "en")


def require_one_language(obj, field: str, message: str) -> None:
    """Posts may be written in Tamil, Malay or English, but not left empty in all three."""
    values = [getattr(obj, f"{field}_{code}", None) for code in LANGUAGE_CODES]
    if not any(v and v.strip() for v in values):
        raise ValidationError({f"{field}_ta": message})


def month_range(first_day: date) -> tuple[datetime, datetime]:
    """Local midnight on the 1st of this month and of the next."""
    next_first = date(first_day.year + first_day.month // 12, first_day.month % 12 + 1, 1)
    return (
        timezone.make_aware(datetime.combine(first_day, time.min)),
        timezone.make_aware(datetime.combine(next_first, time.min)),
    )


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def upcoming(self):
        """Events that haven't finished yet (single-moment events count until they start)."""
        now = timezone.now()
        return self.filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))

    def overlapping(self, start, end):
        """Events running at some point between start and end (end not included)."""
        return self.filter(starts_at__lt=end).filter(
            Q(ends_at__gte=start) | Q(ends_at__isnull=True, starts_at__gte=start)
        )

    def past(self):
        now = timezone.now()
        return self.filter(Q(ends_at__lt=now) | Q(ends_at__isnull=True, starts_at__lt=now))


class Event(models.Model):
    EVENT, HOLIDAY, EXAM, PIBG, SPORTS, CELEBRATION = (
        "event",
        "holiday",
        "exam",
        "pibg",
        "sports",
        "celebration",
    )
    KINDS = [
        (EVENT, _("Event")),
        (HOLIDAY, _("Holiday")),
        (EXAM, _("Exam")),
        (PIBG, _("PIBG")),
        (SPORTS, _("Sports")),
        (CELEBRATION, _("Celebration")),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField("starts")
    ends_at = models.DateTimeField("ends", null=True, blank=True)
    all_day = models.BooleanField(
        "all day",
        default=False,
        help_text="Times are ignored; set the end date for multi-day events.",
    )
    kind = models.CharField(
        "type",
        max_length=20,
        choices=KINDS,
        default=EVENT,
        help_text="Holidays and exams stand out on the Events page.",
    )
    image = models.ImageField(upload_to="events/", blank=True)
    is_published = models.BooleanField("published", default=True)
    notified_at = models.DateTimeField(null=True, blank=True, editable=False)
    source_import = models.ForeignKey(
        "EventImport",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portal:event_detail", args=[self.pk])

    @property
    def is_happening(self) -> bool:
        now = timezone.now()
        return self.starts_at <= now and (self.ends_at is None or self.ends_at >= now)

    def clean(self) -> None:
        require_one_language(self, "title", "Give the event a title in at least one language.")
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "The end must be after the start."})

    def save(self, *args, **kwargs) -> None:
        self.image = shrink_new_upload(self.image)
        if self.all_day:
            # All-day events run from local midnight on the first day to the end of the last day.
            start = timezone.localtime(self.starts_at)
            end = timezone.localtime(self.ends_at) if self.ends_at else start
            self.starts_at = start.replace(hour=0, minute=0, second=0, microsecond=0)
            self.ends_at = end.replace(hour=23, minute=59, second=59, microsecond=0)
        super().save(*args, **kwargs)


class EventImport(models.Model):
    """One spreadsheet upload. Its events stay drafts until staff publish them on the review page."""

    file = models.FileField(upload_to="imports/")
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    row_errors = models.JSONField(default=list, blank=True)
    language = models.CharField(
        max_length=5,
        choices=settings.LANGUAGES,
        default="ta",
        help_text="The language the spreadsheet is written in; its text is saved under it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "event import"

    def __str__(self) -> str:
        return f"{self.original_name} ({self.created_at:%d %b %Y})"


class AnnouncementQuerySet(models.QuerySet):
    def published(self):
        """Published announcements whose publish time has arrived (allows scheduling)."""
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_pinned = models.BooleanField("pinned", default=False, help_text="Pinned items stay on top.")
    is_published = models.BooleanField("published", default=True)
    published_at = models.DateTimeField(
        "publish at", default=timezone.now, help_text="Set a future time to schedule it."
    )

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-is_pinned", "-published_at"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portal:announcement_detail", args=[self.pk])

    def clean(self) -> None:
        require_one_language(self, "title", "Give the update a title in at least one language.")
        require_one_language(self, "body", "Write the update in at least one language.")


class Album(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event = models.ForeignKey(
        Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="albums"
    )
    is_published = models.BooleanField("published", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("portal:album_detail", args=[self.pk])

    def clean(self) -> None:
        require_one_language(self, "title", "Give the album a title in at least one language.")

    @property
    def cover(self):
        return self.photos.first()


class Photo(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="gallery/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.caption or f"Photo {self.pk}"

    def save(self, *args, **kwargs) -> None:
        self.image = shrink_new_upload(self.image)
        super().save(*args, **kwargs)


class StaffMember(models.Model):
    """An email address allowed to sign in to the admin with Google.

    The Django user is created the first time the person signs in. Turning off
    "can sign in" (or deleting the entry) deactivates that user straight away.
    """

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(
        "can sign in", default=True, help_text="Untick to remove this person's access."
    )
    user = models.OneToOneField(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_member",
        editable=False,
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["email"]
        verbose_name = "staff member"

    def __str__(self) -> str:
        return self.name or self.email

    def save(self, *args, **kwargs) -> None:
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
        if self.user_id and self.user.is_active != self.is_active:
            self.user.is_active = self.is_active
            self.user.save(update_fields=["is_active"])


@receiver(post_delete, sender=StaffMember)
def _deactivate_removed_staff(sender, instance, **kwargs):
    if instance.user_id and not instance.user.is_superuser:
        instance.user.is_active = False
        instance.user.save(update_fields=["is_active"])


class Subscriber(models.Model):
    """A parent or guardian who gets an email when staff announce an event."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField("subscribed", default=True)
    language = models.CharField(
        "email language",
        max_length=5,
        choices=settings.LANGUAGES,
        default="ta",
        help_text="Emails are sent in this language: the one the parent used to sign up.",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_unsubscribe_url(self) -> str:
        return reverse("portal:unsubscribe", args=[self.token])


class SocialLinkQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class SocialLink(models.Model):
    """A school page on a social network, listed in the footer of every page."""

    PLATFORMS = [
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("tiktok", "TikTok"),
        ("whatsapp", "WhatsApp"),
        ("telegram", "Telegram"),
        ("x", "X"),
        ("other", "Other"),
    ]

    platform = models.CharField(max_length=20, choices=PLATFORMS)
    url = models.URLField(
        "link",
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="The full address, e.g. https://www.facebook.com/yourschool",
    )
    label = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional name to show instead of the platform, e.g. “PIBG Facebook group”. "
        "Required for “Other”.",
    )
    order = models.PositiveSmallIntegerField(default=0, help_text="Lower numbers come first.")
    is_published = models.BooleanField("published", default=True)

    objects = SocialLinkQuerySet.as_manager()

    class Meta:
        ordering = ["order", "platform", "pk"]
        verbose_name = "social media link"

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.label.strip() or self.get_platform_display()

    def clean(self) -> None:
        if self.platform == "other" and not self.label.strip():
            raise ValidationError({"label": "Give a name for links to other sites."})


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


class DocumentStorage(FileSystemStorage):
    """Keeps Tamil file names readable.

    Django's default clean-up drops Tamil vowel signs, so "சுற்றறிக்கை.pdf" would be saved as
    "சறறறகக.pdf". This keeps letters, marks and digits in any script.
    """

    def get_valid_name(self, name):
        name = str(name).strip().replace(" ", "_")
        name = "".join(c for c in name if unicodedata.category(c)[0] in "LMN" or c in "-_.")
        return name if name.strip(".") else "document"


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
        storage=DocumentStorage(),
        max_length=255,
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
        # Only once the save is committed: a rolled-back save still points at the old file.
        storage = instance.file.storage
        transaction.on_commit(lambda: storage.delete(old))


@receiver(post_delete, sender=Document)
def _delete_document_file(sender, instance, **kwargs):
    if instance.file:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name))


PHONE_HELP = "Enter a Malaysian phone number, for example 03-8723 1234 or 012-345 6789."


def malaysian_number(value: str) -> str:
    """'03-8723 1234' -> '60387231234', the international form links need."""
    digits = re.sub(r"[\s\-.()]", "", value).removeprefix("+")
    if not (digits.isascii() and digits.isdigit()):  # plain 0-9 only, not ௩ or ３
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


def _checked_number(value: str) -> str:
    """The international form, or "" for an empty or unusable number.

    The admin refuses bad numbers, but one stored some other way must not break the page.
    """
    try:
        return malaysian_number(value) if value else ""
    except ValueError:
        return ""


class SchoolContact(models.Model):
    """How parents reach the office. There is only ever one of these."""

    phone = models.CharField(
        max_length=30,
        blank=True,
        validators=[validate_malaysian_number],
        help_text="e.g. 03-8723 1234",
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
        number = _checked_number(self.phone)
        return f"tel:+{number}" if number else ""

    @property
    def whatsapp_link(self) -> str:
        number = _checked_number(self.whatsapp)
        return f"https://wa.me/{number}" if number else ""

    @property
    def email_link(self) -> str:
        return f"mailto:{self.email}" if self.email else ""

    @property
    def google_maps_link(self) -> str:
        if self.map_url:
            return self.map_url
        if self.address:
            return (
                f"https://www.google.com/maps/search/?api=1&query={quote(self._one_line_address)}"
            )
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
