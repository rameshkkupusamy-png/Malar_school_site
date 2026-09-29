from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from portal.staff_list import StaffFileRejected, add_staff_from_rows, read_rows


class Command(BaseCommand):
    help = (
        "Add staff who can sign in with Google, from a spreadsheet with one person per row. "
        "The first email address in each row is used, and the first other filled-in cell as "
        "their name. Existing entries are left as they are."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path, help="Path to an .xlsx or .csv file")

    def handle(self, *args, file: Path, **options):
        if not file.is_file():
            raise CommandError(f"{file} doesn't exist.")
        try:
            with file.open("rb") as handle:
                result = add_staff_from_rows(read_rows(handle, file.name))
        except StaffFileRejected as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"Added {len(result.added)} staff member(s)."))
        if result.already_listed:
            self.stdout.write(f"{len(result.already_listed)} were already on the staff list.")
        if result.rows_without_email:
            rows = ", ".join(str(n) for n in result.rows_without_email[:20])
            self.stdout.write(
                self.style.WARNING(f"No email address found in row(s) {rows}.")
                + " A header row is skipped this way too."
            )
