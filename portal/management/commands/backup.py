import sqlite3
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

PREFIX = "school-backup-"


class Command(BaseCommand):
    help = (
        "Save the database and all uploads (media/ and private_media/) into one zip file in "
        "BACKUP_DIR, "
        "and delete the oldest backups beyond BACKUP_KEEP. Safe to run while the site is up."
    )

    def add_arguments(self, parser):
        parser.add_argument("--to", type=Path, help="Folder for the backup (default BACKUP_DIR)")
        parser.add_argument("--keep", type=int, help="Backups to keep (default BACKUP_KEEP)")

    def handle(self, *args, to: Path | None, keep: int | None, **options):
        folder = to or settings.BACKUP_DIR
        keep = settings.BACKUP_KEEP if keep is None else keep
        folder.mkdir(parents=True, exist_ok=True)

        stamp = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
        target = folder / f"{PREFIX}{stamp}.zip"
        snapshot = folder / f"{PREFIX}{stamp}.sqlite3.tmp"
        try:
            # SQLite's backup API copies a consistent snapshot even while staff are editing.
            connection.ensure_connection()
            with sqlite3.connect(snapshot) as copy:
                connection.connection.backup(copy)
            copy.close()

            folders = [
                (Path(settings.MEDIA_ROOT), "media"),
                (Path(settings.PRIVATE_MEDIA_ROOT), "private_media"),
            ]
            photos = 0
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "db.sqlite3")
                for media, prefix in folders:
                    if not media.is_dir():
                        continue
                    for file in sorted(media.rglob("*")):
                        if file.is_file():
                            # Photos are already compressed; storing them is faster.
                            archive.write(
                                file,
                                Path(prefix) / file.relative_to(media),
                                compress_type=zipfile.ZIP_STORED,
                            )
                            photos += 1
        finally:
            snapshot.unlink(missing_ok=True)

        old = sorted(folder.glob(f"{PREFIX}*.zip"))[:-keep] if keep > 0 else []
        for file in old:
            file.unlink()

        size_mb = target.stat().st_size / 1_000_000
        self.stdout.write(
            self.style.SUCCESS(f"Saved {target} ({size_mb:.1f} MB, {photos} uploaded files).")
        )
        if old:
            self.stdout.write(f"Deleted {len(old)} older backup(s).")
