from django.contrib import admin

from .models import BlogPost, City, ContactEnquiry, FAQ, NewsletterSubscriber, State


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "is_active")
    list_filter = ("state", "is_active")
    search_fields = ("name", "state__name")
    autocomplete_fields = ("state",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_active", "source", "confirmed_at", "created_at")
    list_filter = ("is_active", "source", "created_at")
    search_fields = ("email", "name")
    readonly_fields = (
        "confirmation_token",
        "unsubscribe_token",
        "consent_ip",
        "consent_text",
        "confirmed_at",
        "unsubscribed_at",
        "created_at",
        "updated_at",
    )


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "purpose", "status", "created_at")
    list_filter = ("status", "purpose", "created_at")
    search_fields = ("name", "email", "subject", "message", "organization")
    readonly_fields = ("reference", "consent", "created_at", "updated_at")
    autocomplete_fields = ("handled_by",)
    fieldsets = (
        (None, {"fields": ("reference", "status", "purpose")}),
        ("Contact", {"fields": ("name", "email", "phone", "organization")}),
        ("Message", {"fields": ("subject", "message", "consent")}),
        ("Handling", {"fields": ("admin_notes", "handled_by")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "sort_order", "is_published")
    list_filter = ("category", "is_published")
    search_fields = ("question", "answer", "category")
    list_editable = ("sort_order", "is_published")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "is_featured", "published_at", "author")
    list_filter = ("status", "is_featured", "category", "published_at")
    search_fields = ("title", "excerpt", "content", "seo_title")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "published_at")
    autocomplete_fields = ("author",)
