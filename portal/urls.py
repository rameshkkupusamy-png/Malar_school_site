from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("events/", views.event_list, name="event_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("news/", views.announcement_list, name="announcement_list"),
    path("news/<int:pk>/", views.announcement_detail, name="announcement_detail"),
    path("gallery/", views.album_list, name="album_list"),
    path("gallery/<int:pk>/", views.album_detail, name="album_detail"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("unsubscribe/<uuid:token>/", views.unsubscribe, name="unsubscribe"),
]
