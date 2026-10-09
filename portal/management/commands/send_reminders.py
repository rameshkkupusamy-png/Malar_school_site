from django.core.management.base import BaseCommand

from portal.notifications import reminder_events, send_reminders


class Command(BaseCommand):
    help = (
        "Email every subscriber about the events starting tomorrow. Run it once each evening "
        "(PythonAnywhere: a daily scheduled task at 10:00 UTC, which is 6 pm in Malaysia)."
    )

    def handle(self, *args, **options):
        events = reminder_events()
        sent = send_reminders(events)
        self.stdout.write(f"Sent {sent} reminder email(s) about {len(events)} event(s).")
