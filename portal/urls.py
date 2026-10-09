from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("events/", views.event_list, name="event_list"),
    path("events/calendar.ics", views.calendar_feed, name="calendar_feed"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/calendar.ics", views.event_calendar, name="event_calendar"),
    path("news/", views.announcement_list, name="announcement_list"),
    path("news/<int:pk>/", views.announcement_detail, name="announcement_detail"),
    path("gallery/", views.album_list, name="album_list"),
    path("gallery/<int:pk>/", views.album_detail, name="album_detail"),
    path("documents/", views.document_list, name="document_list"),
    path("documents/<int:pk>/", views.document_open, name="document_open"),
    path("contact/", views.contact, name="contact"),
    path("achievements/", views.achievement_list, name="achievement_list"),
    path("achievements/<int:pk>/", views.achievement_detail, name="achievement_detail"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("unsubscribe/<uuid:token>/", views.unsubscribe, name="unsubscribe"),
]
