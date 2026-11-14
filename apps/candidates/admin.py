from django.contrib import admin

from .models import (
    CandidateProfile,
    Certification,
    Publication,
    Qualification,
    ResearchExperience,
    TeachingExperience,
)


class QualificationInline(admin.TabularInline):
    model = Qualification
    extra = 0
    fields = ("level", "degree", "specialization", "institution", "year_completed")


class TeachingExperienceInline(admin.TabularInline):
    model = TeachingExperience
    extra = 0
    fields = ("designation", "institution", "start_date", "end_date", "is_current")


class ResearchExperienceInline(admin.TabularInline):
    model = ResearchExperience
    extra = 0
    fields = ("role", "institution", "research_area", "start_date", "end_date", "is_current")


class PublicationInline(admin.TabularInline):
    model = Publication
    extra = 0
    fields = ("title", "venue", "publication_type", "year", "is_peer_reviewed")


class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 0
    fields = ("name", "issuing_organization", "issue_date", "expiry_date")


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "headline",
        "highest_qualification",
        "phd_status",
        "is_open_to_work",
        "completion_percentage",
        "updated_at",
    )
    list_filter = ("phd_status", "is_open_to_work", "share_profile_with_recruiters")
    search_fields = ("user__email", "user__full_name", "headline", "specialization", "current_institution")
    autocomplete_fields = ("user", "department", "preferred_designation", "preferred_state", "preferred_city")
    readonly_fields = ("created_at", "updated_at")
    inlines = [
        QualificationInline,
        TeachingExperienceInline,
        ResearchExperienceInline,
        PublicationInline,
        CertificationInline,
    ]


@admin.register(Qualification)
class QualificationAdmin(admin.ModelAdmin):
    list_display = ("profile", "level", "degree", "institution", "year_completed")
    list_filter = ("level", "year_completed")
    search_fields = ("profile__user__email", "profile__user__full_name", "degree", "institution")
    autocomplete_fields = ("profile",)


@admin.register(TeachingExperience)
class TeachingExperienceAdmin(admin.ModelAdmin):
    list_display = ("profile", "designation", "institution", "start_date", "end_date", "is_current")
    list_filter = ("is_current",)
    search_fields = ("profile__user__email", "designation", "institution")
    autocomplete_fields = ("profile",)


@admin.register(ResearchExperience)
class ResearchExperienceAdmin(admin.ModelAdmin):
    list_display = ("profile", "role", "institution", "research_area", "is_current")
    list_filter = ("is_current",)
    search_fields = ("profile__user__email", "role", "institution", "research_area")
    autocomplete_fields = ("profile",)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "publication_type", "year", "indexing", "is_peer_reviewed")
    list_filter = ("publication_type", "is_peer_reviewed", "year")
    search_fields = ("title", "authors", "venue", "profile__user__email")
    autocomplete_fields = ("profile",)


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "issuing_organization", "issue_date", "expiry_date")
    list_filter = ("issuing_organization",)
    search_fields = ("name", "issuing_organization", "profile__user__email")
    autocomplete_fields = ("profile",)
