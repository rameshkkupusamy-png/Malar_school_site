"""Everything written before the site had three languages was in English: file it under English."""

from django.db import migrations

FIELDS = {
    "Event": ["title", "description", "location"],
    "Announcement": ["title", "body"],
    "Album": ["title", "description"],
    "Photo": ["caption"],
}


def copy_to_english(apps, schema_editor):
    for model_name, fields in FIELDS.items():
        model = apps.get_model("portal", model_name)
        for obj in model.objects.all():
            changed = []
            for field in fields:
                value = getattr(obj, field)
                if value and not getattr(obj, f"{field}_en"):
                    setattr(obj, f"{field}_en", value)
                    changed.append(f"{field}_en")
            if changed:
                obj.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("portal", "0004_translations")]

    operations = [migrations.RunPython(copy_to_english, migrations.RunPython.noop)]
