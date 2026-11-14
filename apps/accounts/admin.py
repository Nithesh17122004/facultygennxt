from django import forms
from django.contrib import admin

from .models import AccountDeletionRequest, User


class UserAdminForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to keep the current password. Use at least 10 characters.",
        label="Set a new password",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "full_name",
            "mobile",
            "role",
            "email_verified_at",
            "terms_accepted_at",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserAddForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        help_text="At least 10 characters.",
    )
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email", "full_name", "mobile", "role", "is_active"]

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    add_form = UserAddForm
    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "role",
        "is_active",
        "is_staff",
        "email_verified_at",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "email_verified_at")
    search_fields = ("email", "full_name", "mobile")
    readonly_fields = (
        "date_joined",
        "updated_at",
        "last_login",
        "last_seen_at",
        "failed_login_attempts",
        "locked_until",
    )
    fieldsets = (
        (None, {"fields": ("email", "new_password")}),
        ("Profile", {"fields": ("full_name", "mobile", "role")}),
        ("Verification", {"fields": ("email_verified_at", "terms_accepted_at")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Security", {"fields": ("failed_login_attempts", "locked_until", "last_seen_at", "last_login")}),
        ("Dates", {"fields": ("date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "mobile", "role", "is_active", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs["form"] = self.add_form
        return super().get_form(request, obj, change=change, **kwargs)


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "requested_at", "processed_at", "processed_by")
    list_filter = ("status", "requested_at")
    search_fields = ("user__email", "user__full_name", "reason")
    readonly_fields = ("requested_at",)
    autocomplete_fields = ("user", "processed_by")
