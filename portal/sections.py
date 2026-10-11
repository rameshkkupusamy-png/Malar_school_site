"""Sections of the public site that a superuser can pause (Admin → Site sections)."""

from functools import wraps

from django.shortcuts import render

from .models import SiteSections

KEYS = ("news", "events", "photos", "documents", "pibg", "achievements", "search")


def is_on(key: str) -> bool:
    return getattr(SiteSections.load(), key)


def section(key: str):
    """While the section is paused, the view answers with the paused page (503: temporary)."""
    if key not in KEYS:
        raise ValueError(f"Unknown site section: {key}")

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_on(key):
                return render(request, "portal/section_paused.html", status=503)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
