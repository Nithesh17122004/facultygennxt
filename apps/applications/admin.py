from django.contrib import admin

from .models import (
    Application,
    ApplicationDocument,
    ApplicationNote,
    ApplicationStatusEvent,
    ExternalApplicationClick,
)


class ApplicationDocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 0
    fields = ("document", "label", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("document",)


class ApplicationNoteInline(admin.TabularInline):
    model = ApplicationNote
    extra = 0
    fields = ("author", "note", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)


class ApplicationStatusEventInline(admin.TabularInline):
    model = ApplicationStatusEvent
    extra = 0
    fields = ("from_status", "to_status", "actor", "note", "created_at")
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    can_delete = False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "applied_at", "status_updated_at")
    list_filter = ("status", "applied_at", "job__institution")
    search_fields = ("candidate__email", "candidate__full_name", "job__title", "job__institution__name")
    autocomplete_fields = ("job", "candidate", "resume", "status_updated_by")
    readonly_fields = ("profile_snapshot", "applied_at", "updated_at")
    date_hierarchy = "applied_at"
    inlines = [ApplicationDocumentInline, ApplicationNoteInline, ApplicationStatusEventInline]
    fieldsets = (
        (None, {"fields": ("job", "candidate", "status")}),
        ("Application", {"fields": ("cover_letter", "resume")}),
        ("Workflow", {"fields": ("status_updated_by", "status_updated_at", "withdrawn_at")}),
        ("Snapshot", {"fields": ("profile_snapshot",)}),
        ("Dates", {"fields": ("applied_at", "updated_at")}),
    )


@admin.register(ApplicationDocument)
class ApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ("application", "label", "document", "created_at")
    search_fields = ("application__candidate__email", "application__job__title", "document__original_name")
    autocomplete_fields = ("application", "document")
    readonly_fields = ("created_at",)


@admin.register(ApplicationNote)
class ApplicationNoteAdmin(admin.ModelAdmin):
    list_display = ("application", "author", "created_at")
    search_fields = ("application__candidate__email", "note", "author__email")
    autocomplete_fields = ("application", "author")
    readonly_fields = ("created_at",)


@admin.register(ApplicationStatusEvent)
class ApplicationStatusEventAdmin(admin.ModelAdmin):
    list_display = ("application", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("application__candidate__email", "application__job__title", "note")
    autocomplete_fields = ("application", "actor")
    readonly_fields = ("created_at",)


@admin.register(ExternalApplicationClick)
class ExternalApplicationClickAdmin(admin.ModelAdmin):
    list_display = ("job", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("job__title", "job__institution__name", "user__email")
    autocomplete_fields = ("job", "user")
    readonly_fields = ("job", "user", "session_hash", "created_at")
