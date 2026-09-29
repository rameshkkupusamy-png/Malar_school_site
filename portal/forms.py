from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .imports import build_times


class SubscribeForm(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    name = forms.CharField(label=_("Your name"), max_length=100, required=False)


class EventImportForm(forms.Form):
    file = forms.FileField(
        label="Spreadsheet",
        help_text="Excel (.xlsx) or CSV file, up to 2 MB, using the template's column headings.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.csv"}),
    )
    language = forms.ChoiceField(
        label="Language of this spreadsheet",
        choices=[("ta", "Tamil"), ("ms", "Malay"), ("en", "English")],
        help_text="Titles and places are saved in this language. Add other languages later "
        "by editing each event.",
    )


class StaffImportForm(forms.Form):
    file = forms.FileField(
        label="Spreadsheet",
        help_text="Excel (.xlsx) or CSV file, up to 2 MB, with one teacher per row.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.csv"}),
    )


class DraftEventForm(forms.Form):
    """One editable row on the import review page."""

    event_id = forms.IntegerField(widget=forms.HiddenInput)
    title = forms.CharField(max_length=200)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    start_time = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    end_time = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    location = forms.CharField(max_length=200, required=False)

    @classmethod
    def initial_for(cls, event) -> dict:
        start = timezone.localtime(event.starts_at)
        end = timezone.localtime(event.ends_at) if event.ends_at else None
        return {
            "event_id": event.pk,
            "title": event.title,
            "start_date": start.date(),
            "start_time": None if event.all_day else start.time(),
            "end_date": end.date() if end and end.date() != start.date() else None,
            "end_time": end.time() if end and not event.all_day else None,
            "location": event.location,
        }

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        try:
            cleaned["starts_at"], cleaned["ends_at"], cleaned["all_day"] = build_times(
                cleaned["start_date"],
                cleaned.get("start_time"),
                cleaned.get("end_date"),
                cleaned.get("end_time"),
            )
        except ValueError as error:
            raise forms.ValidationError(f"Check the dates: {error}.") from error
        return cleaned


DraftEventFormSet = forms.formset_factory(DraftEventForm, extra=0)
