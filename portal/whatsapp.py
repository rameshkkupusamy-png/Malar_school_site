"""Share-on-WhatsApp links for the admin.

The link opens WhatsApp with the message already written; staff choose the parents' group
and press send. Nothing is sent from the server.
"""

from urllib.parse import quote

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation

from .models import Announcement, Event

TEMPLATES = {
    Event: "portal/whatsapp/event.txt",
    Announcement: "portal/whatsapp/announcement.txt",
}


def is_public(obj: Event | Announcement) -> bool:
    """Parents can open the post, so the link in the message works."""
    if isinstance(obj, Announcement):
        return obj.is_published and obj.published_at <= timezone.now()
    return obj.is_published


def share_message(obj: Event | Announcement) -> str:
    # The group gets one message, in the site's default language (Tamil). Post text falls
    # back to whichever language staff wrote it in.
    with translation.override(settings.LANGUAGE_CODE):
        context = {"post": obj, "url": settings.SITE_URL + obj.get_absolute_url()}
        if isinstance(obj, Event):
            # The shared date partial ends with a newline, which would leave a blank line.
            context["when"] = render_to_string("portal/_event_time.html", {"event": obj}).strip()
        text = render_to_string(TEMPLATES[type(obj)], context)
    return text.strip()


def share_url(obj: Event | Announcement) -> str:
    return "https://wa.me/?text=" + quote(share_message(obj), safe="")
