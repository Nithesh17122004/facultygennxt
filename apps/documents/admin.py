from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "purpose", "mime_type", "size", "is_deleted", "created_at")
    list_filter = ("purpose", "is_deleted", "mime_type", "created_at")
    search_fields = ("original_name", "owner__email", "owner__full_name", "description")
    readonly_fields = (
        "owner",
        "file",
        "original_name",
        "mime_type",
        "size",
        "checksum",
        "purpose",
        "description",
        "is_deleted",
        "deleted_at",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        # Documents are created through upload flows that enforce validation.
        return False

    def has_change_permission(self, request, obj=None):
        return False
