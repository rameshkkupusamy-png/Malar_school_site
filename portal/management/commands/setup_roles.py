from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

EDITOR_GROUP = "Editors"

# Editors manage all content; they can see subscribers but not change them.
EDITOR_PERMISSIONS = {
    "event": ["add", "change", "delete", "view"],
    "announcement": ["add", "change", "delete", "view"],
    "album": ["add", "change", "delete", "view"],
    "photo": ["add", "change", "delete", "view"],
    "eventimport": ["view", "delete"],
    "subscriber": ["view"],
    "sociallink": ["add", "change", "delete", "view"],
    "document": ["add", "change", "delete", "view"],
}


class Command(BaseCommand):
    help = f"Create or update the '{EDITOR_GROUP}' group for staff who update the portal."

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
        codenames = [
            f"{action}_{model}"
            for model, actions in EDITOR_PERMISSIONS.items()
            for action in actions
        ]
        permissions = Permission.objects.filter(
            content_type__app_label="portal", codename__in=codenames
        )
        group.permissions.set(permissions)
        self.stdout.write(
            self.style.SUCCESS(f"'{EDITOR_GROUP}' group has {permissions.count()} permissions.")
        )
