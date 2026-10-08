import re
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .ical import build_calendar
from .models import Album, Announcement, Document, Event, SchoolContact, Subscriber, month_range

PAGE_SIZE = 10


def home(request):
    # News leads the page: the pinned update (or the latest one) fills the big top section.
    # With no news at all, the next event takes its place.
    news = list(Announcement.objects.published()[:4])
    lead_news = news[0] if news else None
    upcoming = list(Event.objects.published().upcoming()[:5])
    hero_event = upcoming[0] if upcoming and lead_news is None else None
    coming_up = [e for e in upcoming if e != hero_event][:4]

    albums_with_photos = Album.objects.filter(is_published=True, photos__isnull=False).distinct()
    featured_album = albums_with_photos.prefetch_related("photos").first()
    album_photos = list(featured_album.photos.all()) if featured_album else []

    # The big top photo: the event's own picture when an event leads, else the newest album's
    # first photo. The photo band further down uses a different picture from that album.
    hero_image = hero_credit = None
    if hero_event and hero_event.image:
        hero_image = hero_event.image
    elif album_photos:
        hero_image = album_photos[0].image
        hero_credit = album_photos[0].caption
    band_photos = [p for p in album_photos if p.image != hero_image] or album_photos

    return render(
        request,
        "portal/home.html",
        {
            "lead_news": lead_news,
            "more_news": news[1:],
            "hero_event": hero_event,
            "coming_up": coming_up,
            "hero_image": hero_image,
            "hero_credit": hero_credit,
            "featured_album": featured_album,
            "band_photo": band_photos[0] if band_photos else None,
            "subscribe_form": SubscribeForm(),
        },
    )


MONTH_PARAM = re.compile(r"^(\d{4})-(\d{2})$")
FILTERS = [
    ("", gettext_lazy("All")),
    (Event.HOLIDAY, gettext_lazy("Holidays")),
    (Event.EXAM, gettext_lazy("Exams")),
    (Event.PIBG, gettext_lazy("PIBG")),
    (Event.SPORTS, gettext_lazy("Sports")),
    (Event.CELEBRATION, gettext_lazy("Celebrations")),
]


def chosen_month(value: str | None) -> date:
    """The month in ?month=YYYY-MM, or this month."""
    match = MONTH_PARAM.match(value or "")
    if match:
        year, month = int(match[1]), int(match[2])
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return date(year, month, 1)
    return timezone.localdate().replace(day=1)


def add_months(first_day: date, months: int) -> date:
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_query(first_day: date, kind: str) -> str:
    params = {"month": f"{first_day:%Y-%m}"}
    if kind:
        params["type"] = kind
    return "?" + urlencode(params)


def event_list(request):
    month = chosen_month(request.GET.get("month"))
    kind = request.GET.get("type", "")
    if kind not in {key for key, _label in FILTERS}:
        kind = ""

    events = Event.objects.published()
    if kind:
        events = events.filter(kind=kind)
    start, end = month_range(month)
    month_events = list(events.overlapping(start, end).order_by("starts_at"))

    next_month_with_events = None
    if not month_events:
        later = events.filter(starts_at__gte=end).order_by("starts_at").first()
        if later:
            next_month_with_events = timezone.localtime(later.starts_at).date().replace(day=1)

    # Calendar apps subscribe with webcal://, so phones keep checking for new events.
    feed = settings.SITE_URL + reverse("portal:calendar_feed")
    webcal = "webcal://" + feed.split("://", 1)[-1]
    return render(
        request,
        "portal/event_list.html",
        {
            "month": month,
            "events": month_events,
            "filters": [(label, month_query(month, key), key == kind) for key, label in FILTERS],
            "previous_url": month_query(add_months(month, -1), kind),
            "next_url": month_query(add_months(month, 1), kind),
            "next_month_with_events": next_month_with_events,
            "next_month_with_events_url": (
                month_query(next_month_with_events, kind) if next_month_with_events else ""
            ),
            "webcal_url": webcal,
            "google_calendar_url": "https://calendar.google.com/calendar/r?cid="
            + quote(webcal, safe=""),
        },
    )


def event_detail(request, pk):
    event = get_object_or_404(Event.objects.published(), pk=pk)
    albums = event.albums.filter(is_published=True)
    return render(request, "portal/event_detail.html", {"event": event, "albums": albums})


def calendar_response(body: str, filename: str) -> HttpResponse:
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def event_calendar(request, pk):
    """One event as a calendar file, in the language the parent is reading the site in."""
    event = get_object_or_404(Event.objects.published(), pk=pk)
    return calendar_response(build_calendar([event]), f"event-{event.pk}.ics")


def calendar_feed(request):
    """Every published event from the last three months on, for parents' phone calendars.

    Calendar apps fetch this without the visitor's language cookie, so it's always in the
    site's default language (Tamil), falling back to whatever staff wrote.
    """
    since = timezone.now() - timedelta(days=90)
    events = Event.objects.published().filter(starts_at__gte=since)
    with translation.override(settings.LANGUAGE_CODE):
        body = build_calendar(events, name=settings.SCHOOL_NAME)
    return calendar_response(body, "school-events.ics")


def announcement_list(request):
    page = Paginator(Announcement.objects.published(), PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "portal/announcement_list.html", {"page": page})


def announcement_detail(request, pk):
    announcement = get_object_or_404(Announcement.objects.published(), pk=pk)
    return render(request, "portal/announcement_detail.html", {"announcement": announcement})


def album_list(request):
    albums = Album.objects.filter(is_published=True).prefetch_related("photos")
    page = Paginator(albums, 12).get_page(request.GET.get("page"))
    return render(request, "portal/album_list.html", {"page": page})


def album_detail(request, pk):
    album = get_object_or_404(Album.objects.filter(is_published=True), pk=pk)
    return render(request, "portal/album_detail.html", {"album": album})


def document_list(request):
    documents = list(Document.objects.published())
    groups = [(label, [d for d in documents if d.group == key]) for key, label in Document.GROUPS]
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


def contact(request):
    return render(request, "portal/contact.html", {"contact": SchoolContact.load()})


@require_POST
def subscribe(request):
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Enter a valid email address to get event emails."))
        return redirect("portal:home")

    # Emails go out in the language the parent is reading the site in.
    subscriber, created = Subscriber.objects.get_or_create(
        email__iexact=form.cleaned_data["email"],
        defaults={
            "email": form.cleaned_data["email"],
            "name": form.cleaned_data["name"],
            "language": request.LANGUAGE_CODE,
        },
    )
    if not created:
        subscriber.is_active = True
        subscriber.language = request.LANGUAGE_CODE
        subscriber.save(update_fields=["is_active", "language"])
    messages.success(
        request,
        _("You'll get an email at %(email)s when events are added.") % {"email": subscriber.email},
    )
    return redirect("portal:home")


def unsubscribe(request, token):
    subscriber = get_object_or_404(Subscriber, token=token)
    if request.method == "POST":
        subscriber.is_active = False
        subscriber.save(update_fields=["is_active"])
        messages.success(
            request, _("%(email)s won't get event emails any more.") % {"email": subscriber.email}
        )
        return redirect("portal:home")
    return render(request, "portal/unsubscribe.html", {"subscriber": subscriber})
