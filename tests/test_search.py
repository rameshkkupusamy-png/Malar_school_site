from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone, translation

from portal.models import Achievement, Album, Announcement, Document, Event
from portal.search import LIMIT, find, words


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def event(days=7, **fields):
    return Event.objects.create(starts_at=timezone.now() + timedelta(days=days), **fields)


def titles(sections, key):
    found = {section.key: section for section in sections}
    return [item.title for item in found[key].items] if key in found else []


def test_words_trims_cuts_and_limits():
    assert words("  sports   day ") == ["sports", "day"]
    assert words("a") == []
    assert words("   ") == []
    assert words("one two three four five six") == ["one", "two", "three", "four", "five"]
    assert len("".join(words("x" * 500))) == 100


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["title_ta", "title_ms", "title_en"])
def test_finds_a_word_in_any_language_column(field):
    event(**{field: "Hari sukan விளையாட்டு"})
    assert len(find("விளையாட்டு")) == 1
    assert len(find("sukan")) == 1


@pytest.mark.django_db
def test_searches_every_content_type_and_its_fields():
    event(title="Concert", location_en="Main hall")
    Announcement.objects.create(title="Notice", body_en="Bring a hall pass")
    Document.objects.create(
        title="Form",
        note_en="Hall booking form",
        group=Document.LIST,
        file=SimpleUploadedFile("form.pdf", b"%PDF-1.4"),
    )
    Achievement.objects.create(
        title="Choir",
        description_en="Sang in the town hall",
        category=Achievement.ARTS,
        level=Achievement.DISTRICT,
    )
    Album.objects.create(title="Hall opening")

    with translation.override("en"):
        sections = find("hall")

    assert [s.key for s in sections] == ["events", "news", "documents", "achievements", "photos"]
    assert [s.heading for s in sections] == [
        "Events",
        "News",
        "Documents",
        "Achievements",
        "Photos",
    ]
    assert all(s.total == 1 for s in sections)


@pytest.mark.django_db
def test_every_word_must_match_and_case_is_ignored():
    event(title_en="Sports day")
    event(title_en="Sports meeting")
    assert titles(find("SPORTS DAY"), "events") == ["Sports day"]
    assert titles(find("  sports   day "), "events") == ["Sports day"]


@pytest.mark.django_db
def test_hidden_content_is_never_found():
    event(title="Hidden draft", is_published=False)
    Announcement.objects.create(title="Hidden draft", body="x", is_published=False)
    Announcement.objects.create(
        title="Hidden scheduled", body="x", published_at=timezone.now() + timedelta(days=1)
    )
    Document.objects.create(
        title="Hidden expired",
        group=Document.LIST,
        file=SimpleUploadedFile("old.pdf", b"%PDF-1.4"),
        remove_after=timezone.localdate() - timedelta(days=1),
    )
    Achievement.objects.create(
        title="Hidden draft",
        category=Achievement.ARTS,
        level=Achievement.DISTRICT,
        is_published=False,
    )
    Album.objects.create(title="Hidden draft", is_published=False)

    assert find("hidden") == []


@pytest.mark.django_db
def test_pupil_names_are_not_searched():
    win = Achievement.objects.create(
        title="Gold, state choir", category=Achievement.ARTS, level=Achievement.STATE
    )
    win.pupils.create(name="Kavin a/l Raju", class_name="5 Mutiara", consent=True)
    assert find("Kavin") == []


@pytest.mark.django_db
def test_wildcard_characters_match_literally():
    event(title="Sports day")
    assert find("%%") == []
    assert find("__") == []


@pytest.mark.django_db
def test_upcoming_and_happening_events_come_before_past_ones():
    now = timezone.now()
    event(days=-30, title="Fair past")
    event(days=10, title="Fair later")
    event(days=2, title="Fair soon")
    Event.objects.create(
        title="Fair now", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2)
    )
    event(days=-5, title="Fair recent")

    assert titles(find("fair"), "events") == [
        "Fair now",
        "Fair soon",
        "Fair later",
        "Fair recent",
        "Fair past",
    ]


@pytest.mark.django_db
def test_news_is_newest_first_even_when_pinned():
    now = timezone.now()
    Announcement.objects.create(
        title="Fees old", body="x", is_pinned=True, published_at=now - timedelta(days=9)
    )
    Announcement.objects.create(title="Fees new", body="x", published_at=now - timedelta(days=1))
    assert titles(find("fees"), "news") == ["Fees new", "Fees old"]


@pytest.mark.django_db
def test_each_section_keeps_its_count_but_shows_at_most_ten():
    for day in range(LIMIT + 3):
        event(days=day + 1, title=f"Club meeting {day}")
    [section] = find("club")
    assert section.total == LIMIT + 3
    assert len(section.items) == LIMIT


@pytest.mark.django_db
def test_short_queries_search_nothing():
    event(title="Sports day")
    assert find("") == []
    assert find("s") == []
