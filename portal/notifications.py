from django.conf import settings
from django.core.mail import EmailMessage, mailers
from django.template.loader import render_to_string
from django.utils import timezone, translation

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
