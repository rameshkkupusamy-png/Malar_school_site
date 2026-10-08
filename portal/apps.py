from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"
    verbose_name = "School portal"

    def ready(self):
        # Lets Pillow, and so the photo upload fields, open iPhone HEIC photos.
        from pillow_heif import register_heif_opener

        register_heif_opener()
