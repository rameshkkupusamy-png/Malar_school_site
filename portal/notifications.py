from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.mail import EmailMessage, mailers
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from .models import Event, Subscriber


def notify_subscribers(event: Event) -> int:
    """Email every active subscriber about an event. Returns the number of emails sent."""
    messages = []
    for subscriber in Subscriber.objects.filter(is_active=True):
        # Each parent gets the email, and the event text, in the language they signed up in.
        with translation.override(subscriber.language):
            body = render_to_string(
                "portal/email/new_event.txt",
                {
                    "event": event,
                    "subscriber": subscriber,
                    "school_name": settings.SCHOOL_NAME,
                    "event_url": settings.SITE_URL + event.get_absolute_url(),
                    "unsubscribe_url": settings.SITE_URL + subscriber.get_unsubscribe_url(),
                },
            )
            subject = f"{settings.SCHOOL_NAME}: {event.title}"
        messages.append(EmailMessage(subject, body, to=[subscriber.email]))

    if messages:
        with mailers.default as connection:
            connection.send_messages(messages)

    event.notified_at = timezone.now()
    event.save(update_fields=["notified_at"])
    return len(messages)


def reminder_events() -> list[Event]:
    """Published events starting tomorrow (school time) that haven't had a reminder yet."""
    tomorrow = timezone.localdate() + timedelta(days=1)
    start = timezone.make_aware(datetime.combine(tomorrow, time.min))
    end = start + timedelta(days=1)
    return list(
        Event.objects.published()
        .filter(starts_at__gte=start, starts_at__lt=end, reminded_at__isnull=True)
        .order_by("starts_at")
    )


def send_reminders(events: list[Event] | None = None) -> int:
    """Email every active subscriber one list of tomorrow's events. Returns the emails sent.

    Each event is reminded once: it's marked as soon as the emails have gone.
    """
    events = reminder_events() if events is None else events
    if not events:
        return 0
    messages = []
    for subscriber in Subscriber.objects.filter(is_active=True):
        with translation.override(subscriber.language):
            # The date partial ends with a newline, which would leave a blank line in the email.
            items = [
                {
                    "event": e,
                    "when": render_to_string("portal/_event_time.html", {"event": e}).strip(),
                    "url": settings.SITE_URL + e.get_absolute_url(),
                }
                for e in events
            ]
            body = render_to_string(
                "portal/email/reminder.txt",
                {
                    "items": items,
                    "subscriber": subscriber,
                    "school_name": settings.SCHOOL_NAME,
                    "unsubscribe_url": settings.SITE_URL + subscriber.get_unsubscribe_url(),
                },
            )
            subject = f"{settings.SCHOOL_NAME}: {_('Tomorrow at school')}"
        messages.append(EmailMessage(subject, body, to=[subscriber.email]))

    if messages:
        with mailers.default as connection:
            connection.send_messages(messages)

    Event.objects.filter(pk__in=[e.pk for e in events]).update(reminded_at=timezone.now())
    return len(messages)
