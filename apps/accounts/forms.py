from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.core.forms import StyledFormMixin

from .validators import normalize_mobile

User = get_user_model()


class CandidateRegistrationForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label="Full name",
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "As on your academic records"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )
    mobile = forms.CharField(
        max_length=15,
        label="Mobile number",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "10-digit Indian mobile"}),
    )
    password1 = forms.CharField(
        label="Create password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 10 characters. Avoid common or personal passwords.",
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    terms = forms.BooleanField(
        label="I accept the Terms and Conditions and Privacy Policy",
        error_messages={"required": "Please accept the terms to create an account."},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Try signing in instead.")
        return email

    def clean_mobile(self):
        mobile = normalize_mobile(self.cleaned_data["mobile"])
        if User.objects.filter(mobile=mobile).exists():
            raise ValidationError("This mobile number is already linked to an account.")
        return mobile

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1:
            candidate = User(
                email=cleaned.get("email", ""),
                full_name=cleaned.get("full_name", ""),
                role=User.Role.CANDIDATE,
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        from django.utils import timezone

        return User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            full_name=self.cleaned_data["full_name"],
            mobile=self.cleaned_data["mobile"],
            role=User.Role.CANDIDATE,
            terms_accepted_at=timezone.now(),
        )


class LoginForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    remember = forms.BooleanField(
        label="Keep me signed in on this device",
        required=False,
    )


class ResendVerificationForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class PasswordResetRequestForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class SetNewPasswordForm(StyledFormMixin, DjangoSetPasswordForm):
    pass


class ChangePasswordForm(StyledFormMixin, DjangoPasswordChangeForm):
    pass


class AccountIdentityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "mobile"]
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "mobile": forms.TextInput(attrs={"autocomplete": "tel"}),
        }

    def clean_mobile(self):
        mobile = self.cleaned_data.get("mobile")
        if not mobile:
            return None
        mobile = normalize_mobile(mobile)
        if User.objects.filter(mobile=mobile).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This mobile number is already linked to another account.")
        return mobile


class AccountDeletionForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="Confirm your password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    reason = forms.CharField(
        label="Reason (optional)",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Help us understand why you are leaving."}),
    )
    confirmation = forms.CharField(
        label='Type "DELETE MY ACCOUNT" to confirm',
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user or not self.user.check_password(password):
            raise ValidationError("Your password is incorrect.")
        return password

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip().upper()
        if value != "DELETE MY ACCOUNT":
            raise ValidationError('Type "DELETE MY ACCOUNT" exactly to confirm.')
        return value


class MFADisableForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    token = forms.CharField(
        label="Authenticator code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "placeholder": "000000",
            }
        ),
    )
