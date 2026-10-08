from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import translation
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .forms import DraftEventForm, DraftEventFormSet, EventImportForm, StaffImportForm
from .imports import FileRejected, build_template, parse_file
from .models import (
    Album,
    Announcement,
    Event,
    EventImport,
    Photo,
    SocialLink,
    StaffMember,
    Subscriber,
)
from .notifications import notify_subscribers
from .staff_list import MAX_BYTES, StaffFileRejected, add_staff_from_rows, read_rows
from .whatsapp import is_public, share_url

admin.site.site_header = f"{settings.SCHOOL_NAME} admin"
admin.site.site_title = f"{settings.SCHOOL_NAME} admin"
admin.site.index_title = "Manage the school portal"
admin.site.login_template = "admin/staff_login.html"


def in_all_languages(*fields):
    """Search every language version of these fields."""
    return [f"{field}_{code}" for field in fields for code in ("ta", "ms", "en")]


class WhatsAppShareMixin:
    """A "Share on WhatsApp" button on the list and edit pages of published posts."""

    @admin.display(description="WhatsApp")
    def whatsapp_share(self, obj):
        if obj is None or obj.pk is None:
            return "Save and publish first, then share."
        if not is_public(obj):
            return "Not shown to parents yet, so it can't be shared."
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">Share on WhatsApp</a>',
            share_url(obj),
        )


@admin.register(Event)
class EventAdmin(WhatsAppShareMixin, TranslationAdmin):
    list_display = [
        "title",
        "starts_at",
        "all_day",
        "location",
        "is_published",
        "notified_at",
        "whatsapp_share",
    ]
    list_filter = ["is_published", "all_day", "starts_at"]
    search_fields = in_all_languages("title", "description", "location")
    date_hierarchy = "starts_at"
    readonly_fields = ["notified_at", "whatsapp_share"]
    actions = ["email_subscribers"]
    change_list_template = "admin/portal/event/change_list.html"

    @admin.action(description="Email subscribers about selected events")
    def email_subscribers(self, request, queryset):
        unpublished = queryset.filter(is_published=False).count()
        sent = 0
        for event in queryset.filter(is_published=True):
            sent += notify_subscribers(event)
        if unpublished:
            self.message_user(
                request,
                f"Skipped {unpublished} unpublished event(s). Publish them first.",
                messages.WARNING,
            )
        self.message_user(request, f"Sent {sent} email(s).", messages.SUCCESS)

    # Spreadsheet import -------------------------------------------------------------

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("import/", view(self.import_view), name="portal_event_import"),
            path(
                "import/template.xlsx",
                view(self.import_template_view),
                name="portal_event_import_template",
            ),
            path(
                "import/<int:pk>/review/",
                view(self.import_review_view),
                name="portal_event_import_review",
            ),
        ] + super().get_urls()

    def _check_import_permission(self, request):
        if not (self.has_add_permission(request) and self.has_change_permission(request)):
            raise PermissionDenied

    def _context(self, request, title, **extra):
        return {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": title,
            **extra,
        }

    def import_template_view(self, request):
        self._check_import_permission(request)
        response = HttpResponse(
            build_template(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="event-import-template.xlsx"'
        return response

    def import_view(self, request):
        self._check_import_permission(request)
        form = EventImportForm(request.POST or None, request.FILES or None)
        file_errors = []
        row_errors = []

        if request.method == "POST" and form.is_valid():
            uploaded = form.cleaned_data["file"]
            try:
                result = parse_file(uploaded)
            except FileRejected as error:
                file_errors.append(str(error))
            else:
                if not result.events:
                    file_errors.append("No events could be imported from this file.")
                    row_errors = result.errors
                else:
                    uploaded.seek(0)
                    language = form.cleaned_data["language"]
                    # The spreadsheet's text is filed under the language staff picked.
                    with transaction.atomic(), translation.override(language):
                        batch = EventImport.objects.create(
                            file=uploaded,
                            original_name=uploaded.name,
                            uploaded_by=request.user,
                            row_errors=result.errors,
                            language=language,
                        )
                        for parsed in result.events:
                            Event.objects.create(
                                title=parsed.title,
                                starts_at=parsed.starts_at,
                                ends_at=parsed.ends_at,
                                all_day=parsed.all_day,
                                location=parsed.location,
                                description=parsed.description,
                                is_published=False,
                                source_import=batch,
                            )
                    self.message_user(
                        request,
                        f"Found {len(result.events)} event(s). Check them below, then publish.",
                        messages.SUCCESS,
                    )
                    return redirect("admin:portal_event_import_review", pk=batch.pk)

        return TemplateResponse(
            request,
            "admin/portal/event/import.html",
            self._context(
                request,
                "Import events from a spreadsheet",
                form=form,
                file_errors=file_errors,
                row_errors=row_errors,
                recent_imports=EventImport.objects.all()[:5],
            ),
        )

    def import_review_view(self, request, pk):
        self._check_import_permission(request)
        batch = get_object_or_404(EventImport, pk=pk)
        # Show and save the text in the language the spreadsheet was written in.
        with translation.override(batch.language):
            return self._import_review(request, batch)

    def _import_review(self, request, batch):
        drafts = batch.events.filter(is_published=False).order_by("starts_at")
        drafts_by_id = {event.pk: event for event in drafts}
        selected_ids = {int(i) for i in request.POST.getlist("selected") if i.isdigit()}
        selected_ids &= drafts_by_id.keys()
        action = request.POST.get("action")

        if request.method == "POST" and action == "delete":
            count = len(selected_ids)
            batch.events.filter(pk__in=selected_ids).delete()
            self.message_user(request, f"Deleted {count} draft event(s).", messages.SUCCESS)
            return redirect("admin:portal_event_import_review", pk=batch.pk)

        if request.method == "POST":
            formset = DraftEventFormSet(request.POST)
            if formset.is_valid():
                to_publish = []
                with transaction.atomic():
                    for row in formset.cleaned_data:
                        event = drafts_by_id.get(row["event_id"])
                        if event is None:
                            continue
                        event.title = row["title"]
                        event.starts_at = row["starts_at"]
                        event.ends_at = row["ends_at"]
                        event.all_day = row["all_day"]
                        event.location = row["location"]
                        if action == "publish" and event.pk in selected_ids:
                            event.is_published = True
                            to_publish.append(event)
                        event.save()

                if action == "publish":
                    if not to_publish:
                        self.message_user(
                            request, "Tick the events you want to publish.", messages.WARNING
                        )
                    else:
                        note = f"Published {len(to_publish)} event(s)."
                        if request.POST.get("email_parents"):
                            sent = sum(notify_subscribers(event) for event in to_publish)
                            note += f" Sent {sent} email(s) to parents."
                        self.message_user(request, note, messages.SUCCESS)
                else:
                    self.message_user(request, "Saved your changes.", messages.SUCCESS)
                return redirect("admin:portal_event_import_review", pk=batch.pk)
        else:
            formset = DraftEventFormSet(
                initial=[DraftEventForm.initial_for(event) for event in drafts]
            )

        published_count = batch.events.filter(is_published=True).count()
        return TemplateResponse(
            request,
            "admin/portal/event/import_review.html",
            self._context(
                request,
                f"Review events from {batch.original_name} ({batch.get_language_display()})",
                batch=batch,
                formset=formset,
                selected_ids={str(i) for i in selected_ids},
                published_count=published_count,
            ),
        )


@admin.register(EventImport)
class EventImportAdmin(admin.ModelAdmin):
    list_display = ["original_name", "uploaded_by", "created_at", "draft_count", "review_link"]
    readonly_fields = ["original_name", "file", "uploaded_by", "created_at", "row_errors"]

    def has_add_permission(self, request):
        return False  # uploads go through Events > Import from spreadsheet

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="drafts left")
    def draft_count(self, obj):
        return obj.events.filter(is_published=False).count()

    @admin.display(description="")
    def review_link(self, obj):
        url = reverse("admin:portal_event_import_review", args=[obj.pk])
        return format_html('<a href="{}">Review</a>', url)


@admin.register(Announcement)
class AnnouncementAdmin(WhatsAppShareMixin, TranslationAdmin):
    list_display = ["title", "published_at", "is_pinned", "is_published", "whatsapp_share"]
    readonly_fields = ["whatsapp_share"]
    list_editable = ["is_pinned", "is_published"]
    list_filter = ["is_pinned", "is_published"]
    search_fields = in_all_languages("title", "body")
    date_hierarchy = "published_at"


class PhotoInline(TranslationTabularInline):
    model = Photo
    extra = 3
    fields = ["image", "caption", "order"]


@admin.register(Album)
class AlbumAdmin(TranslationAdmin):
    list_display = ["title", "event", "is_published", "created_at"]
    list_filter = ["is_published"]
    search_fields = in_all_languages("title")
    autocomplete_fields = ["event"]
    inlines = [PhotoInline]


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "is_active", "last_sign_in", "added_at"]
    list_editable = ["is_active"]
    list_filter = ["is_active"]
    search_fields = ["email", "name"]
    fields = ["email", "name", "is_active"]
    actions = ["remove_access"]

    change_list_template = "admin/portal/staffmember/change_list.html"

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("import/", view(self.import_view), name="portal_staffmember_import"),
        ] + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = StaffImportForm(request.POST or None, request.FILES or None)
        error = None
        if request.method == "POST" and form.is_valid():
            uploaded = form.cleaned_data["file"]
            try:
                if uploaded.size > MAX_BYTES:
                    raise StaffFileRejected(
                        "The file is over 2 MB. Remove extra sheets or columns."
                    )
                result = add_staff_from_rows(read_rows(uploaded.file, uploaded.name))
            except StaffFileRejected as rejected:
                error = str(rejected)
            else:
                note = f"Added {len(result.added)} staff member(s)."
                if result.already_listed:
                    note += f" {len(result.already_listed)} were already on the list."
                self.message_user(request, note, messages.SUCCESS)
                if result.rows_without_email:
                    rows = ", ".join(str(n) for n in result.rows_without_email[:20])
                    self.message_user(
                        request,
                        f"No email address in row(s) {rows}, so they were skipped. "
                        "A heading row is skipped this way too.",
                        messages.WARNING,
                    )
                return redirect("admin:portal_staffmember_changelist")
        return TemplateResponse(
            request,
            "admin/portal/staffmember/import.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Add staff from a spreadsheet",
                "form": form,
                "error": error,
            },
        )

    @admin.display(description="last signed in")
    def last_sign_in(self, obj):
        return obj.user.last_login if obj.user_id and obj.user.last_login else "Never"

    @admin.action(description="Remove sign-in access for selected staff")
    def remove_access(self, request, queryset):
        for member in queryset:
            member.is_active = False
            member.save()
        self.message_user(
            request, f"Removed access for {queryset.count()} staff member(s).", messages.SUCCESS
        )


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "language", "is_active", "created_at"]
    list_filter = ["is_active", "language"]
    search_fields = ["email", "name"]


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ["name", "platform", "url", "order", "is_published"]
    list_display_links = ["name"]
    list_editable = ["order", "is_published"]
    list_filter = ["platform", "is_published"]
    search_fields = ["label", "url"]
    fields = ["platform", "label", "url", "order", "is_published"]
