from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from waitress import serve

from school_portal.wsgi import application


class Command(BaseCommand):
    help = (
        "Run the site with the Waitress web server, for hosting it on a Windows computer. "
        "It only listens on this computer; Cloudflare Tunnel carries visitors to it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--threads", type=int, default=8)

    def handle(self, *args, host: str, port: int, threads: int, **options):
        if settings.DEBUG:
            raise CommandError(
                "DJANGO_DEBUG is on. Set DJANGO_DEBUG=0 in .env before serving the site "
                "to the public (use runserver for development)."
            )
        self.stdout.write(f"Serving {settings.SITE_URL} on http://{host}:{port}/ (Ctrl+C stops)")
        serve(application, host=host, port=port, threads=threads)
