from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import Album, Announcement, Event, Subscriber

PAGE_SIZE = 10


def home(request):
    upcoming = list(Event.objects.published().upcoming()[:4])
    return render(
        request,
        "portal/home.html",
        {
            "next_event": upcoming[0] if upcoming else None,
            "later_events": upcoming[1:],
            "announcements": Announcement.objects.published()[:5],
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
        messages.error(request, "Enter a valid email address to get event emails.")
        return redirect("portal:home")

    subscriber, created = Subscriber.objects.get_or_create(
        email__iexact=form.cleaned_data["email"],
        defaults={"email": form.cleaned_data["email"], "name": form.cleaned_data["name"]},
    )
    if not created and not subscriber.is_active:
        subscriber.is_active = True
        subscriber.save(update_fields=["is_active"])
    messages.success(request, f"You'll get an email at {subscriber.email} when events are added.")
    return redirect("portal:home")


def unsubscribe(request, token):
    subscriber = get_object_or_404(Subscriber, token=token)
    if request.method == "POST":
        subscriber.is_active = False
        subscriber.save(update_fields=["is_active"])
        messages.success(request, f"{subscriber.email} won't get event emails any more.")
        return redirect("portal:home")
    return render(request, "portal/unsubscribe.html", {"subscriber": subscriber})
