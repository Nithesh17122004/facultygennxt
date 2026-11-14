from django.contrib import admin

from .models import Institution, InstitutionDocument, Recruiter


class InstitutionDocumentInline(admin.TabularInline):
    model = InstitutionDocument
    extra = 0
    fields = ("doc_type", "document", "status", "notes", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("document", "uploaded_by")


class RecruiterInline(admin.TabularInline):
    model = Recruiter
    extra = 0
    fields = ("user", "designation", "is_primary", "is_active")
    autocomplete_fields = ("user",)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "institution_type",
        "city",
        "state",
        "verification_status",
        "is_active",
        "created_at",
    )
    list_filter = ("verification_status", "institution_type", "is_active", "state")
    search_fields = ("name", "official_email", "website", "contact_person", "city__name")
    readonly_fields = ("slug", "verified_at", "verified_by", "created_at", "updated_at")
    autocomplete_fields = ("state", "city", "verified_by")
    inlines = [InstitutionDocumentInline, RecruiterInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "website", "logo", "institution_type", "established_year")}),
        ("Location", {"fields": ("address", "state", "city", "pincode")}),
        ("Contact", {"fields": ("official_email", "phone", "contact_person", "contact_designation", "contact_phone", "contact_email")}),
        ("Profile", {"fields": ("description", "is_active")}),
        ("Verification", {"fields": ("verification_status", "verification_notes", "verified_at", "verified_by")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(InstitutionDocument)
class InstitutionDocumentAdmin(admin.ModelAdmin):
    list_display = ("institution", "doc_type", "status", "uploaded_by", "created_at")
    list_filter = ("doc_type", "status")
    search_fields = ("institution__name", "document__original_name")
    autocomplete_fields = ("institution", "document", "uploaded_by")
    readonly_fields = ("created_at",)


@admin.register(Recruiter)
class RecruiterAdmin(admin.ModelAdmin):
    list_display = ("user", "institution", "designation", "is_primary", "is_active", "created_at")
    list_filter = ("is_primary", "is_active", "institution")
    search_fields = ("user__email", "user__full_name", "institution__name", "designation")
    autocomplete_fields = ("user", "institution", "invited_by")
    readonly_fields = ("created_at", "updated_at")
