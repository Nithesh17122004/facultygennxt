from django.contrib import admin

from .models import EmailLog, EmailPreference, JobAlertDelivery, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "category", "level", "is_read", "created_at")
    list_filter = ("category", "level", "is_read", "created_at")
    search_fields = ("recipient__email", "title", "message")
    autocomplete_fields = ("recipient",)
    readonly_fields = ("created_at", "read_at")


@admin.register(EmailPreference)
class EmailPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "job_alerts", "application_updates", "institution_updates", "marketing", "updated_at")
    list_filter = ("job_alerts", "application_updates", "institution_updates", "marketing")
    search_fields = ("user__email", "user__full_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("updated_at",)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("subject", "recipient_email", "template", "category", "status", "provider", "attempts", "created_at")
    list_filter = ("status", "category", "provider", "created_at")
    search_fields = ("recipient_email", "subject", "template", "error", "provider_message_id")
    readonly_fields = (
        "recipient_email",
        "user",
        "subject",
        "template",
        "category",
        "status",
        "provider",
        "provider_message_id",
        "rendered_html",
        "rendered_text",
        "error",
        "attempts",
        "created_at",
        "sent_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(JobAlertDelivery)
class JobAlertDeliveryAdmin(admin.ModelAdmin):
    list_display = ("alert", "job", "sent_at")
    list_filter = ("sent_at",)
    search_fields = ("alert__name", "alert__user__email", "job__title")
    autocomplete_fields = ("alert", "job")
    readonly_fields = ("sent_at",)

    def has_add_permission(self, request):
        return False
