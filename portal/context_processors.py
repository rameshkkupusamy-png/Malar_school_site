from django.conf import settings


def school(request):
    return {"school_name": settings.SCHOOL_NAME}
