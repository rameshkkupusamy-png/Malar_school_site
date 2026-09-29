from django.conf import settings


def school(request):
    return {
        "school_name": settings.SCHOOL_NAME,
        "school_motto": settings.SCHOOL_MOTTO,
        "google_sign_in": bool(settings.GOOGLE_CLIENT_ID),
    }
