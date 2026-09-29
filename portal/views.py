from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import Album, Announcement, Event, Subscriber

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


def event_list(request):
    show_past = request.GET.get("show") == "past"
    events = Event.objects.published()
    events = events.past().order_by("-starts_at") if show_past else events.upcoming()
    page = Paginator(events, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "portal/event_list.html", {"page": page, "show_past": show_past})


def event_detail(request, pk):
    event = get_object_or_404(Event.objects.published(), pk=pk)
    albums = event.albums.filter(is_published=True)
    return render(request, "portal/event_detail.html", {"event": event, "albums": albums})


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
