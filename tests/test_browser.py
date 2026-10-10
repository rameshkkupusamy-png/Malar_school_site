"""Browser checks: every public page loads cleanly and fits a phone screen.

Run with the rest of the suite (`pytest`). The first time, install the browser with
`python -m playwright install chromium`.
"""

import os
from datetime import timedelta

import pytest
from django.utils import timezone

from portal.models import (
    Achievement,
    Album,
    Announcement,
    CommitteeMember,
    Event,
    Pibg,
    Subscriber,
    UrgentNotice,
)

# Playwright's sync API runs an event loop in the test thread, which Django's ORM
# otherwise refuses to share. The data is created before the browser does anything.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PHONE = {"width": 360, "height": 800}  # small Android phones; Tamil text is widest here
DESKTOP = {"width": 1280, "height": 800}


@pytest.fixture
def site(transactional_db):
    now = timezone.now()
    event = Event.objects.create(
        title="Annual science fair with a long name to test wrapping on small screens",
        location="Main hall",
        description="Families are welcome from 10:00.",
        starts_at=now + timedelta(days=3),
        ends_at=now + timedelta(days=3, hours=4),
    )
    Event.objects.create(title="Sports day", starts_at=now + timedelta(days=10), all_day=True)
    Event.objects.create(title="Summer concert", starts_at=now - timedelta(days=30))
    # This month's holiday and exam, so the month view renders its band and labels.
    Event.objects.create(title="Deepavali holiday", starts_at=now, all_day=True, kind=Event.HOLIDAY)
    Event.objects.create(title="UPSA exam week", starts_at=now, all_day=True, kind=Event.EXAM)
    achievement = Achievement.objects.create(
        title="மாநில அளவிலான திருக்குறள் ஒப்பித்தல் போட்டியில் தங்கப் பதக்கம்",
        category=Achievement.TAMIL,
        level=Achievement.STATE,
    )
    achievement.pupils.create(
        name="Thirunavukkarasu a/l Kandasamy", class_name="6 Mutiara", consent=True
    )
    UrgentNotice.objects.create(
        message_ta="வெள்ளம் காரணமாக இன்று பள்ளி மூடப்பட்டுள்ளது. திங்கள்கிழமை வகுப்புகள் வழக்கம்போல் நடைபெறும்.",
        link="https://example.com/news/1/",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    news = Announcement.objects.create(
        title="School closed on Friday", body="Classes resume on Monday.", is_pinned=True
    )
    album = Album.objects.create(title="Sports day photos", event=event)
    Event.objects.create(
        title="PIBG annual general meeting", starts_at=now + timedelta(days=12), kind=Event.PIBG
    )
    pibg = Pibg.objects.create(
        term="2026/2027",
        about_ta="ஆண்டுக் கட்டணம் RM20. பள்ளி அலுவலகத்தில் செலுத்தலாம். தன்னார்வலர்களை வரவேற்கிறோம்.",
        phone="012-345 6789",
        email="pibg.ladangsemenyih@example.com",
        whatsapp_group="https://chat.whatsapp.com/abc",
    )
    pibg.committee.create(name="Encik Arunachalam a/l Subramaniam", role=CommitteeMember.CHAIR)
    pibg.committee.create(name="Puan Kavitha", role=CommitteeMember.ASSISTANT_TREASURER)
    return {"event": event, "news": news, "album": album, "achievement": achievement}


def use_language(page, live_server, language):
    """Pretend the visitor picked this language in the switcher."""
    page.context.add_cookies(
        [{"name": "django_language", "value": language, "url": live_server.url}]
    )


def page_paths(site):
    return [
        "/",
        "/events/",
        "/events/?type=holiday",
        site["event"].get_absolute_url(),
        "/news/",
        site["news"].get_absolute_url(),
        "/gallery/",
        site["album"].get_absolute_url(),
        "/documents/",
        "/pibg/",
        "/contact/",
        "/achievements/",
        site["achievement"].get_absolute_url(),
        "/search/?q=sports",
    ]


def collect_errors(page):
    """Console errors and failed requests, ignoring the missing favicon."""
    errors = []
    page.on(
        "console",
        lambda msg: msg.type == "error" and "favicon" not in msg.text and errors.append(msg.text),
    )
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


@pytest.mark.parametrize("language", ["ta", "ms", "en"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_public_pages_load_without_errors_or_sideways_scroll(
    page, live_server, site, viewport, language
):
    use_language(page, live_server, language)
    page.set_viewport_size(viewport)
    errors = collect_errors(page)

    for path in page_paths(site):
        response = page.goto(live_server.url + path)
        assert response.status == 200, path

        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 0, f"{path} scrolls sideways by {overflow}px at {viewport['width']}px"

    assert errors == []


def test_every_page_has_a_title_and_one_main_heading(page, live_server, site):
    for path in page_paths(site):
        page.goto(live_server.url + path)
        assert page.title(), path
        assert page.locator("h1").count() == 1, path


def test_parent_can_sign_up_for_event_emails(page, live_server, site):
    use_language(page, live_server, "en")
    page.set_viewport_size(PHONE)
    page.goto(live_server.url + "/")

    page.get_by_label("Email address").fill("parent@example.com")
    page.get_by_role("button", name="Sign up for emails").click()

    page.get_by_text("You'll get an email at parent@example.com").wait_for()
    assert Subscriber.objects.filter(email="parent@example.com", is_active=True).exists()


def test_keyboard_focus_is_visible(page, live_server, site):
    page.goto(live_server.url + "/")
    page.keyboard.press("Tab")

    outline = page.evaluate(
        """() => {
            const style = getComputedStyle(document.activeElement);
            return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0;
        }"""
    )
    assert outline, "The first focused link has no visible focus outline"


def test_urgent_bar_is_yellow_and_its_label_pulses(page, live_server, site):
    page.goto(live_server.url + "/")

    bar = page.evaluate("getComputedStyle(document.querySelector('.urgent')).backgroundColor")
    assert bar == "rgb(242, 213, 60)"  # torch yellow
    label = page.locator(".urgent-label")
    assert label.evaluate("el => getComputedStyle(el).animationName") == "urgent-pulse"
    assert label.evaluate("el => getComputedStyle(el).animationIterationCount") == "3"


def test_urgent_pulse_is_skipped_when_the_phone_asks_for_less_motion(page, live_server, site):
    page.emulate_media(reduced_motion="reduce")
    page.goto(live_server.url + "/")

    label = page.locator(".urgent-label")
    assert label.evaluate("el => getComputedStyle(el).animationName") == "none"


def test_links_in_the_urgent_bar_show_keyboard_focus(page, live_server, site):
    page.goto(live_server.url + "/")
    link = page.locator(".urgent a")
    link.focus()
    colour = link.evaluate("el => getComputedStyle(el).outlineColor")
    assert colour != "rgb(242, 213, 60)", "a yellow outline is invisible on the yellow bar"


def test_parent_can_search_and_open_a_result(page, live_server, site):
    use_language(page, live_server, "en")
    page.set_viewport_size(PHONE)
    page.goto(live_server.url + "/")

    page.get_by_role("navigation", name="Main").get_by_role("link", name="Search").click()
    page.get_by_label("What are you looking for?").fill("science fair")
    page.get_by_role("button", name="Search").click()
    page.get_by_role("link", name=site["event"].title).click()

    assert page.url == live_server.url + site["event"].get_absolute_url()
