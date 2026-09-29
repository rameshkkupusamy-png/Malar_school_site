from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("language/", include("django.conf.urls.i18n")),
    path("", include("portal.urls")),
]


def media(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += [re_path(rf"^{settings.MEDIA_URL.strip('/')}/(?P<path>.*)$", media)]
