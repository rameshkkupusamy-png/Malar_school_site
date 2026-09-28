"""Read events from an uploaded spreadsheet (.xlsx or .csv).

Each row becomes a draft event; problems are reported per row so staff can fix the file
or correct the drafts on the review page.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time

from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from .models import Event

COLUMNS = ["Title", "Start date", "Start time", "End date", "End time", "Location", "Description"]
REQUIRED = ("Title", "Start date")
MAX_ROWS = 500
MAX_FILE_SIZE = 2 * 1024 * 1024

# Day-first, as used by most schools outside the US. The template says so.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"]
TIME_FORMATS = ["%H:%M", "%H.%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]


class FileRejected(Exception):
    """The whole file can't be read (wrong type, missing columns, too big)."""


@dataclass
class ParsedEvent:
    row: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    location: str = ""
    description: str = ""


@dataclass
class ParseResult:
    events: list[ParsedEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - only the date part is used
        except ValueError:
            continue
    raise ValueError(f"'{text}' isn't a date. Use a format like 14/10/2026")


def parse_time(value) -> time | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    if isinstance(value, float) and 0 <= value < 1:  # Excel stores times as a fraction of a day
        seconds = min(round(value * 86400), 86399)
        return time(seconds // 3600, seconds % 3600 // 60, seconds % 60)
    text = str(value).strip().upper().replace(".M.", "M").replace("A.M", "AM").replace("P.M", "PM")
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()  # noqa: DTZ007 - only the time part is used
        except ValueError:
            continue
    raise ValueError(f"'{value}' isn't a time. Use a format like 09:30 or 2:30 PM")


def build_times(
    start_date: date, start_time: time | None, end_date: date | None, end_time: time | None
) -> tuple[datetime, datetime | None, bool]:
    """Turn spreadsheet-style date and time cells into (starts_at, ends_at, all_day).

    No start time means an all-day event (multi-day if an end date is given).
    """
    all_day = start_time is None
    starts_at = timezone.make_aware(datetime.combine(start_date, start_time or time.min))
    if all_day:
        ends_at = timezone.make_aware(datetime.combine(end_date or start_date, time(23, 59, 59)))
    elif end_date or end_time:
        ends_at = timezone.make_aware(
            datetime.combine(end_date or start_date, end_time or time(23, 59, 59))
        )
    else:
        ends_at = None
    if ends_at and ends_at < starts_at:
        raise ValueError("it ends before it starts")
    return starts_at, ends_at, all_day


def _read_rows(uploaded_file) -> list[list]:
    name = uploaded_file.name.lower()
    if uploaded_file.size > MAX_FILE_SIZE:
        raise FileRejected("The file is larger than 2 MB. Split it into smaller files.")
    if name.endswith(".xlsx"):
        try:
            workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
        except Exception as error:
            raise FileRejected("The file couldn't be opened as an Excel workbook.") from error
        sheet = workbook.active
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    if name.endswith(".csv"):
        text = uploaded_file.read().decode("utf-8-sig", errors="replace")
        return [row for row in csv.reader(io.StringIO(text))]
    raise FileRejected("Upload an Excel (.xlsx) or CSV (.csv) file.")


def _column_positions(header: list) -> dict[str, int]:
    wanted = {name.lower(): name for name in COLUMNS}
    positions = {}
    for index, cell in enumerate(header):
        key = str(cell or "").strip().rstrip("*").strip().lower()
        if key in wanted:
            positions[wanted[key]] = index
    missing = [name for name in REQUIRED if name not in positions]
    if missing:
        raise FileRejected(
            f"The first row must contain the column headings. Missing: {', '.join(missing)}. "
            "Download the template to see the expected headings."
        )
    return positions


def parse_file(uploaded_file) -> ParseResult:
    """Parse an uploaded file. Raises FileRejected if the file as a whole is unusable."""
    rows = _read_rows(uploaded_file)
    if not rows:
        raise FileRejected("The file is empty.")
    positions = _column_positions(rows[0])
    data_rows = rows[1:]
    if len(data_rows) > MAX_ROWS:
        raise FileRejected(f"The file has more than {MAX_ROWS} rows. Split it into smaller files.")

    result = ParseResult()
    seen = set()
    for row_number, row in enumerate(data_rows, start=2):

        def cell(column, row=row):
            index = positions.get(column)
            if index is None or index >= len(row):
                return None
            value = row[index]
            return value.strip() if isinstance(value, str) else value

        if all(value in (None, "") for value in row):
            continue

        title = str(cell("Title") or "").strip()
        if not title:
            result.errors.append(f"Row {row_number}: the title is missing.")
            continue
        try:
            start_date = parse_date(cell("Start date"))
            if start_date is None:
                raise ValueError("the start date is missing")
            starts_at, ends_at, all_day = build_times(
                start_date,
                parse_time(cell("Start time")),
                parse_date(cell("End date")),
                parse_time(cell("End time")),
            )
        except ValueError as error:
            result.errors.append(f"Row {row_number} ({title}): {error}.")
            continue

        key = (title.lower(), starts_at.date())
        if key in seen:
            result.errors.append(f"Row {row_number} ({title}): appears twice in the file. Skipped.")
            continue
        seen.add(key)

        local_day = timezone.localtime(starts_at).date()
        if Event.objects.filter(title__iexact=title, starts_at__date=local_day).exists():
            result.errors.append(
                f"Row {row_number} ({title}): an event with this title already exists on "
                f"{local_day:%d %b %Y}. Skipped."
            )
            continue

        result.events.append(
            ParsedEvent(
                row=row_number,
                title=title[:200],
                starts_at=starts_at,
                ends_at=ends_at,
                all_day=all_day,
                location=str(cell("Location") or "")[:200],
                description=str(cell("Description") or ""),
            )
        )
    return result


def build_template() -> bytes:
    """An .xlsx template with the expected headings and a sheet of instructions."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Events"
    sheet.append(COLUMNS)
    for column_cells, width in zip(sheet.columns, [34, 14, 12, 14, 12, 22, 50], strict=True):
        column_cells[0].font = Font(bold=True)
        sheet.column_dimensions[column_cells[0].column_letter].width = width
    sheet.freeze_panes = "A2"

    help_sheet = workbook.create_sheet("How to fill this in")
    lines = [
        ["Fill in one event per row on the Events sheet. Keep the headings in the first row."],
        [],
        ["Title and Start date are required. Everything else is optional."],
        ["Dates: day first, e.g. 14/10/2026 or 2026-10-14."],
        ["Times: 24-hour or AM/PM, e.g. 14:30 or 2:30 PM."],
        ["Leave Start time empty for an all-day event, e.g. a holiday."],
        ["For a multi-day event, fill in End date, e.g. exam week."],
        [],
        ["Examples:"],
        COLUMNS,
        ["Science fair", "14/10/2026", "10:00", "", "14:00", "Main hall", "Families welcome."],
        ["Diwali holidays", "20/10/2026", "", "24/10/2026", "", "", "School closed."],
        [],
        ["After uploading, every event is a draft until you tick it and click Publish."],
    ]
    for line in lines:
        help_sheet.append(line)
    help_sheet.column_dimensions["A"].width = 34
    help_sheet["A1"].font = Font(bold=True)

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
