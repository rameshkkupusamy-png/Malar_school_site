from django.conf import settings
from django.utils import translation
from django.utils.cache import patch_vary_headers

# Django's own admin screens are only partly translated into Tamil, so staff pages start in
# English unless the person has picked a language in the site's switcher.
STAFF_PATHS = ("/admin/", "/accounts/")


class SiteLanguageMiddleware:
    """Use the language the visitor picked in the header, or Tamil.

    Unlike Django's LocaleMiddleware this ignores the browser's language on purpose:
    the school wants every first-time visitor to see the site in Tamil.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.languages = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        chosen = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if chosen in self.languages:
            language = chosen
        elif request.path.startswith(STAFF_PATHS):
            language = "en"
        else:
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        patch_vary_headers(response, ["Cookie"])
        return response
