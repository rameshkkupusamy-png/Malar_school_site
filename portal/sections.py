"""Sections of the public site that a superuser can pause (Admin → Site sections)."""

from contextvars import ContextVar
from functools import wraps

from django.shortcuts import render

from .models import SiteSections

KEYS = ("news", "events", "photos", "documents", "pibg", "achievements", "search")


# Holds the record for the length of one web request (see SiteSectionsMiddleware), so the menu,
# the view and the admin list read it once. Outside a request every check reads it fresh.
_request_cache: ContextVar[dict | None] = ContextVar("site_sections", default=None)


def current() -> SiteSections:
    cache = _request_cache.get()
    if cache is None:
        return SiteSections.load()
    if "record" not in cache:
        cache["record"] = SiteSections.load()
    return cache["record"]


def is_on(key: str) -> bool:
    return getattr(current(), key)


class SiteSectionsMiddleware:
    """Reads Site sections at most once per request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request_cache.set({})
        try:
            return self.get_response(request)
        finally:
            _request_cache.reset(token)


def paused_page(request):
    return render(request, "portal/section_paused.html", status=503)


def section(key: str):
    """While the section is paused, the view answers with the paused page (503: temporary)."""
    if key not in KEYS:
        raise ValueError(f"Unknown site section: {key}")

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_on(key):
                return paused_page(request)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
