"""Calendar files (.ics) so parents can put school events on their phones.

Written by hand rather than with a library: the format is small, and this keeps the
hosting setup free of extra packages. See RFC 5545.
"""

from collections.abc import Iterable
from datetime import UTC, timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

from .models import Event

MAX_LINE_BYTES = 75


def escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


def fold(line: str) -> str:
    """Split lines longer than 75 bytes, never in the middle of a (Tamil) character."""
    parts, current, size = [], "", 0
    for char in line:
        length = len(char.encode())
        if size + length > MAX_LINE_BYTES:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += length
    parts.append(current)
    return "\r\n".join(parts)


def utc(moment) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def event_lines(event: Event) -> list[str]:
    url = settings.SITE_URL + event.get_absolute_url()
    host = urlparse(settings.SITE_URL).hostname or "localhost"
    if event.all_day:
        first = timezone.localtime(event.starts_at).date()
        last = timezone.localtime(event.ends_at or event.starts_at).date()
        # The end date is exclusive: the day after the event ends.
        times = [
            f"DTSTART;VALUE=DATE:{first:%Y%m%d}",
            f"DTEND;VALUE=DATE:{last + timedelta(days=1):%Y%m%d}",
        ]
    else:
        end = event.ends_at or event.starts_at + timedelta(hours=1)
        times = [f"DTSTART:{utc(event.starts_at)}", f"DTEND:{utc(end)}"]

    # Many calendar apps hide the URL field, so the link goes in the description too.
    description = f"{event.description}\n\n{url}" if event.description else url
    lines = [
        "BEGIN:VEVENT",
        f"UID:event-{event.pk}@{host}",
        f"DTSTAMP:{utc(event.updated_at)}",
        *times,
        f"SUMMARY:{escape(event.title)}",
    ]
    if event.location:
        lines.append(f"LOCATION:{escape(event.location)}")
    lines += [f"DESCRIPTION:{escape(description)}", f"URL:{url}", "END:VEVENT"]
    return lines


def build_calendar(events: Iterable[Event], name: str = "") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{escape(settings.SCHOOL_NAME)}//School portal//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if name:
        # Only the subscribed feed is named; a single event joins the parent's own calendar.
        lines += [
            f"X-WR-CALNAME:{escape(name)}",
            f"X-WR-TIMEZONE:{settings.TIME_ZONE}",
            "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
            "X-PUBLISHED-TTL:PT6H",
        ]
    for event in events:
        lines += event_lines(event)
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)
