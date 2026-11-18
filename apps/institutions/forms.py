from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.constants import INSTITUTION_TYPES
from apps.core.forms import StyledFormMixin
from apps.core.models import City, State
from apps.core.widgets import CitySelect
from apps.core.utils import validate_uploaded_document
from apps.documents.models import scan_for_malware
from apps.accounts.validators import normalize_mobile

from .models import Institution, InstitutionDocument, Recruiter

User = get_user_model()


class InstitutionRegistrationForm(StyledFormMixin, forms.Form):
    institution_name = forms.CharField(max_length=240, label="Institution name")
    website = forms.URLField(label="Official website", max_length=500)
    official_email = forms.EmailField(label="Official institutional email")
    contact_person = forms.CharField(max_length=150, label="Contact person")
    contact_designation = forms.CharField(max_length=150, label="Contact person's designation")
    phone = forms.CharField(max_length=25, label="Phone number")
    address = forms.CharField(
        max_length=1000,
        label="Full address",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    state = forms.ModelChoiceField(queryset=State.objects.none(), label="State / UT")
    city = forms.ModelChoiceField(queryset=City.objects.none(), label="City")
    pincode = forms.CharField(max_length=10, required=False, label="PIN code")
    institution_type = forms.ChoiceField(choices=INSTITUTION_TYPES, label="Institution type")
    established_year = forms.IntegerField(
        required=False, min_value=1800, max_value=timezone.localdate().year
    )
    password1 = forms.CharField(
        label="Create password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 10 characters.",
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    authorization_document = forms.FileField(
        label="Authorisation letter",
        help_text="A signed letter authorising this recruiter to publish vacancies. PDF, JPG or PNG up to 5 MB.",
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
    )
    registration_document = forms.FileField(
        label="Registration / affiliation certificate (optional)",
        required=False,
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
    )
    terms = forms.BooleanField(
        label="I accept the Terms and Conditions and Privacy Policy",
        error_messages={"required": "Please accept the terms to continue."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].queryset = State.objects.all().order_by("name")
        self.fields["city"].queryset = City.objects.all().select_related("state").order_by("name")
        self.fields["state"].widget = forms.Select(
            attrs={"data-state-select": "", "data-city-target": "#id_city", "class": "form-select"}
        )
        self.fields["website"].widget.attrs["placeholder"] = "https://institution.ac.in"
        self.fields["official_email"].widget.attrs["placeholder"] = "registrar@institution.ac.in"
        self.fields["phone"].widget.attrs["inputmode"] = "tel"
        self.fields["city"].widget = CitySelect(attrs={"class": "form-select"})

    def clean_official_email(self):
        email = self.cleaned_data["official_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Sign in instead.")
        return email

    def clean_institution_name(self):
        name = self.cleaned_data["institution_name"].strip()
        if Institution.objects.filter(name__iexact=name).exists():
            raise ValidationError("An institution with this name is already registered.")
        return name

    def clean_phone(self):
        return normalize_mobile(self.cleaned_data["phone"])

    def clean_authorization_document(self):
        file = self.cleaned_data["authorization_document"]
        validate_uploaded_document(file)
        if not scan_for_malware(file):
            raise ValidationError("This file could not be scanned and was not uploaded.")
        return file

    def clean_registration_document(self):
        file = self.cleaned_data.get("registration_document")
        if file:
            validate_uploaded_document(file)
            if not scan_for_malware(file):
                raise ValidationError("This file could not be scanned and was not uploaded.")
        return file

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get("city")
        state = cleaned.get("state")
        if city and state and city.state_id != state.pk:
            self.add_error("city", "Choose a city within the selected state.")
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1:
            candidate = User(
                email=cleaned.get("official_email", ""),
                full_name=cleaned.get("contact_person", ""),
                role=User.Role.RECRUITER,
            )
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class InstitutionProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Institution
        fields = [
            "name",
            "website",
            "description",
            "logo",
            "phone",
            "contact_person",
            "contact_designation",
            "contact_phone",
            "contact_email",
            "address",
            "state",
            "city",
            "pincode",
            "institution_type",
            "established_year",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Introduce your institution, academic programmes and campuses."}
            ),
            "address": forms.Textarea(attrs={"rows": 3}),
            "logo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "established_year": forms.NumberInput(attrs={"min": 1800, "max": 2026}),
            "state": forms.Select(
                attrs={"data-state-select": "", "data-city-target": "#id_city", "class": "form-select"}
            ),
            "city": CitySelect(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["state"].queryset = State.objects.filter(is_active=True)
        self.fields["city"].queryset = City.objects.filter(is_active=True).select_related("state")
        verified = self.instance and self.instance.is_verified
        if verified:
            # Identity-critical fields are changed through support to prevent
            # impersonation after verification.
            self.fields["name"].disabled = True
            self.fields["website"].disabled = True
            self.fields["institution_type"].disabled = True
            self.fields["established_year"].disabled = True

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get("city")
        state = cleaned.get("state")
        if city and state and city.state_id != state.pk:
            self.add_error("city", "Choose a city within the selected state.")
        return cleaned


class InstitutionDocumentUploadForm(StyledFormMixin, forms.Form):
    doc_type = forms.ChoiceField(choices=InstitutionDocument.DocType.choices)
    file = forms.FileField(
        label="Document",
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="PDF preferred. JPG or PNG accepted. Maximum 5 MB.",
    )

    def clean_file(self):
        validate_uploaded_document(self.cleaned_data["file"])
        if not scan_for_malware(self.cleaned_data["file"]):
            raise ValidationError("This file could not be scanned and was not uploaded.")
        return self.cleaned_data["file"]


class RecruiterInviteForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    designation = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=25, required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A FacultyNxtGen account already uses this email.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            return normalize_mobile(phone)
        return ""


class RecruiterProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Recruiter
        fields = ["designation", "phone"]

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            return normalize_mobile(phone)
        return ""
