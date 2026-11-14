from django.contrib import admin

from .models import (
    Department,
    Designation,
    Job,
    JobAlert,
    JobReport,
    JobStatusHistory,
    JobView,
    SavedJob,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


class JobStatusHistoryInline(admin.TabularInline):
    model = JobStatusHistory
    extra = 0
    fields = ("from_status", "to_status", "actor", "note", "created_at")
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    can_delete = False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "institution",
        "designation",
        "department",
        "city",
        "status",
        "application_method",
        "deadline",
        "published_at",
    )
    list_filter = (
        "status",
        "employment_type",
        "application_method",
        "state",
        "department",
    )
    search_fields = ("title", "institution__name", "specialization", "source_information")
    readonly_fields = (
        "slug",
        "views_count",
        "published_at",
        "approved_at",
        "approved_by",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "institution",
        "posted_by",
        "designation",
        "department",
        "state",
        "city",
        "notification_document",
    )
    date_hierarchy = "created_at"
    inlines = [JobStatusHistoryInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "institution", "posted_by", "status")}),
        ("Role", {"fields": ("designation", "department", "specialization", "employment_type", "vacancies")}),
        ("Location", {"fields": ("state", "city", "campus_location")}),
        ("Eligibility", {"fields": ("required_qualification", "experience_min", "experience_max", "eligibility")}),
        ("Compensation", {"fields": ("salary_disclosed", "salary_min", "salary_max", "salary_period", "salary_notes")}),
        ("Description", {"fields": ("description", "required_documents", "application_instruction")}),
        ("Application", {"fields": ("application_method", "external_application_url", "external_application_email", "deadline", "publication_date")}),
        ("Official source", {"fields": ("notification_document", "notification_url", "source_information")}),
        ("Verification", {"fields": ("verified_institution", "verified_recruiter", "verified_advertisement", "verified_application_url", "verified_deadline", "verified_eligibility", "review_notes", "rejection_reason", "suspension_reason")}),
        ("Audit", {"fields": ("approved_by", "approved_at", "published_at", "expiry_notified_at", "is_deleted", "deleted_at", "created_at", "updated_at")}),
    )


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "job__title", "job__institution__name")
    autocomplete_fields = ("user", "job")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "frequency", "is_active", "last_sent_at", "created_at")
    list_filter = ("frequency", "is_active", "employment_type")
    search_fields = ("name", "keyword", "user__email")
    autocomplete_fields = ("user", "department", "designation", "state", "city")
    readonly_fields = ("last_sent_at", "created_at", "updated_at")


@admin.register(JobReport)
class JobReportAdmin(admin.ModelAdmin):
    list_display = ("job", "reported_by", "reason", "status", "created_at", "reviewed_by")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("job__title", "reported_by__email", "details")
    autocomplete_fields = ("job", "reported_by", "reviewed_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(JobStatusHistory)
class JobStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("job", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("job__title", "note")
    autocomplete_fields = ("job", "actor")
    readonly_fields = ("job", "from_status", "to_status", "actor", "note", "created_at")


@admin.register(JobView)
class JobViewAdmin(admin.ModelAdmin):
    list_display = ("job", "viewed_on", "created_at")
    list_filter = ("viewed_on",)
    search_fields = ("job__title", "job__institution__name")
    autocomplete_fields = ("job",)
    readonly_fields = ("job", "session_hash", "viewed_on", "created_at")
