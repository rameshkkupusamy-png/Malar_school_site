from django.conf import settings

from .models import SocialLink, UrgentNotice


def school(request):
    return {
        "school_name": settings.SCHOOL_NAME,
        "school_motto": settings.SCHOOL_MOTTO,
        "school_short_name": settings.SCHOOL_SHORT_NAME,
        "google_sign_in": bool(settings.GOOGLE_CLIENT_ID),
        # Lazy: only queried on pages that show the footer.
        "social_links": SocialLink.objects.published(),
        "urgent_notices": UrgentNotice.objects.showing(),
    }
