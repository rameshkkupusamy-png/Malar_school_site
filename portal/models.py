import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class EventQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def upcoming(self):
        """Events that haven't finished yet (single-moment events count until they start)."""
        now = timezone.now()
        return self.filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))

    def past(self):
        now = timezone.now()
        return self.filter(Q(ends_at__lt=now) | Q(ends_at__isnull=True, starts_at__lt=now))


class Event(models.Model):
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
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "The end must be after the start."})

    def save(self, *args, **kwargs) -> None:
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


class Subscriber(models.Model):
    """A parent or guardian who gets an email when staff announce an event."""

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField("subscribed", default=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_unsubscribe_url(self) -> str:
        return reverse("portal:unsubscribe", args=[self.token])
