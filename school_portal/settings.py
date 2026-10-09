"""Django settings. Values that differ between development and production come from
environment variables; the defaults are safe for local development only."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Private values (like the Google client secret) can live in a .env file next to manage.py.
# It is git-ignored. Real environment variables, e.g. on the hosting server, take priority.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, "1" if default else "0").lower() in ("1", "true", "yes")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# School-specific settings
SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "SJK (T) Ladang Semenyih")
SCHOOL_MOTTO = os.environ.get("SCHOOL_MOTTO", "Usaha Tangga Kejayaan")
# The name under the icon on a phone's home screen; only about 12 letters fit.
SCHOOL_SHORT_NAME = os.environ.get("SCHOOL_SHORT_NAME", "SJKT Semenyih")
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

# Behind Cloudflare Tunnel the site is reached over https, but the tunnel talks to the local
# server over plain http and says so in X-Forwarded-Proto. Only trust that header when the site
# is actually behind a proxy, otherwise a visitor could fake it.
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [SITE_URL] if SITE_URL.startswith("https://") else []
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = SITE_URL.startswith("https://")

INSTALLED_APPS = [
    "modeltranslation",  # must come before admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "portal",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves static files when DEBUG is off
    "django.contrib.sessions.middleware.SessionMiddleware",
    "portal.middleware.SiteLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "school_portal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "portal.context_processors.school",
            ],
        },
    },
]

WSGI_APPLICATION = "school_portal.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Staff sign-in: password (site owner) or Google for anyone on the staff list in the admin.
# Google sign-in is switched on by setting GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": GOOGLE_CLIENT_ID,
                "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "key": "",
            }
        ]
        if GOOGLE_CLIENT_ID
        else [],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}
ACCOUNT_ADAPTER = "portal.auth.NoSignupAccountAdapter"
SOCIALACCOUNT_ADAPTER = "portal.auth.StaffListSocialAccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = "admin:index"

# Tamil, Malay and English. Everyone starts in Tamil; the switcher in the header changes it
# (remembered in a cookie). Posts can be written in any of the three: visitors see their
# language, or the first other version that exists.
LANGUAGE_CODE = "ta"
LANGUAGES = [
    ("ta", "தமிழ்"),
    ("ms", "Bahasa Melayu"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
MODELTRANSLATION_DEFAULT_LANGUAGE = "ta"
MODELTRANSLATION_FALLBACK_LANGUAGES = ("ta", "ms", "en")
# Admin labels read "title (Tamil)" rather than "title [ta]".
_LANGUAGE_NAMES = {"ta": "Tamil", "ms": "Malay", "en": "English"}
MODELTRANSLATION_BUILD_LOCALIZED_VERBOSE_NAME = lambda verbose_name, lang: (
    f"{verbose_name} ({_LANGUAGE_NAMES.get(lang, lang)})"
)
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kuala_Lumpur")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
# Uploaded photos are served by Django itself when DEBUG is off. That is fine for a school
# site on its own computer; Cloudflare caches them in front of it.
SERVE_MEDIA = env_bool("DJANGO_SERVE_MEDIA", True)

# Nightly backups (scripts/backup.py): where they go and how many to keep.
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", BASE_DIR / "backups"))
BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email: printed to the console unless EMAIL_HOST is set, then sent over SMTP.
if os.environ.get("EMAIL_HOST"):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.environ["EMAIL_HOST"],
                "port": int(os.environ.get("EMAIL_PORT", "587")),
                "username": os.environ.get("EMAIL_HOST_USER", ""),
                "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
                "use_tls": env_bool("EMAIL_USE_TLS", True),
            },
        },
    }
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"{SCHOOL_NAME} <noreply@example.com>")
