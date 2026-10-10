"""Site search: find published posts by words written in any of the three languages.

Each word must appear in at least one searched field, in any language column (title_ta,
title_ms, title_en, ...). Every section starts from its content type's published queryset, so
drafts, scheduled news and expired documents can never appear. Pupil names (AchievementPupil)
and photo captions are deliberately not searched.
"""

import operator
from dataclasses import dataclass
from functools import reduce

from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _

from .models import Achievement, Album, Announcement, Document, Event

MAX_LENGTH = 100
MIN_LENGTH = 2
MAX_WORDS = 5
LIMIT = 10


@dataclass(frozen=True)
class Section:
    key: str
    heading: str
    total: int
    items: list


def words(query: str) -> list[str]:
    """The words to look for; empty when the query is too short to search."""
    query = query.strip()[:MAX_LENGTH]
    if len(query) < MIN_LENGTH:
        return []
    return query.split()[:MAX_WORDS]


def matching(fields: tuple[str, ...], terms: list[str]) -> Q:
    languages = [code for code, _name in settings.LANGUAGES]
    per_word = [
        reduce(
            operator.or_,
            (Q(**{f"{field}_{lang}__icontains": term}) for field in fields for lang in languages),
        )
        for term in terms
    ]
    return reduce(operator.and_, per_word)


def events(found) -> list:
    """Upcoming (and happening) events soonest first, then past events newest first."""
    items = list(found.upcoming().order_by("starts_at")[:LIMIT])
    if len(items) < LIMIT:
        items += list(found.past().order_by("-starts_at")[: LIMIT - len(items)])
    return items


def find(query: str) -> list[Section]:
    terms = words(query)
    if not terms:
        return []
    searches = [
        ("events", _("Events"), Event.objects.published(), ("title", "description", "location")),
        (
            "news",
            _("News"),
            Announcement.objects.published().order_by("-published_at"),
            ("title", "body"),
        ),
        ("documents", _("Documents"), Document.objects.published(), ("title", "note")),
        (
            "achievements",
            _("Achievements"),
            Achievement.objects.published(),
            ("title", "description"),
        ),
        ("photos", _("Photos"), Album.objects.filter(is_published=True), ("title", "description")),
    ]
    sections = []
    for key, heading, queryset, fields in searches:
        found = queryset.filter(matching(fields, terms))
        total = found.count()
        if total:
            items = events(found) if key == "events" else list(found[:LIMIT])
            sections.append(Section(key, heading, total, items))
    return sections
