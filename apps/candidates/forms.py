from django import forms
from django.core.exceptions import ValidationError

from apps.core.constants import EMPLOYMENT_TYPES
from apps.core.forms import StyledFormMixin, HoneypotMixin
from apps.core.models import City, State
from apps.core.widgets import CitySelect
from apps.documents.models import Document
from apps.jobs.models import Department, Designation
from apps.notifications.models import EmailPreference

from .models import (
    CandidateProfile,
    Certification,
    Publication,
    Qualification,
    ResearchExperience,
    TeachingExperience,
)


class CandidateProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = [
            "headline",
            "bio",
            "highest_qualification",
            "ug_degree",
            "pg_degree",
            "phd_status",
            "phd_thesis_title",
            "specialization",
            "department",
            "teaching_experience_years",
            "research_experience_years",
            "current_designation",
            "current_institution",
            "preferred_state",
            "preferred_city",
            "preferred_designation",
            "preferred_employment_type",
            "avatar",
        ]
        widgets = {
            "headline": forms.TextInput(
                attrs={"placeholder": "Assistant Professor · Computer Science · PhD (Pursuing)"}
            ),
            "bio": forms.Textarea(attrs={"rows": 4, "maxlength": 3000}),
            "highest_qualification": forms.TextInput(
                attrs={"placeholder": "Example: PhD in Computer Science"}
            ),
            "ug_degree": forms.TextInput(attrs={"placeholder": "Example: B.Tech Computer Science"}),
            "pg_degree": forms.TextInput(attrs={"placeholder": "Example: M.Tech Computer Science"}),
            "phd_thesis_title": forms.TextInput(attrs={"placeholder": "Thesis title (optional)"}),
            "specialization": forms.TextInput(
                attrs={"placeholder": "Example: Machine Learning, Data Mining"}
            ),
            "current_designation": forms.TextInput(attrs={"placeholder": "Example: Assistant Professor"}),
            "current_institution": forms.TextInput(attrs={"placeholder": "Current or most recent institution"}),
            "preferred_employment_type": forms.Select(choices=[("", "Any employment type")] + EMPLOYMENT_TYPES),
            "bio": forms.Textarea(attrs={"rows": 4, "maxlength": 3000}),
            "avatar": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "preferred_state": forms.Select(
                attrs={"data-state-select": "", "data-city-target": "#id_preferred_city"}
            ),
            "preferred_city": CitySelect(),
        }
        labels = {
            "phd_status": "PhD status",
            "ug_degree": "UG degree",
            "pg_degree": "PG degree",
            "preferred_state": "Preferred state",
            "preferred_city": "Preferred city",
            "preferred_designation": "Preferred designation",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["preferred_designation"].queryset = Designation.objects.filter(is_active=True)
        self.fields["preferred_state"].queryset = State.objects.filter(is_active=True)
        self.fields["preferred_city"].queryset = City.objects.filter(is_active=True).select_related("state")
        for name in ("department", "preferred_designation", "preferred_state", "preferred_city"):
            self.fields[name].required = False
        self.fields["preferred_employment_type"].required = False

    def clean(self):
        cleaned = super().clean()
        state = cleaned.get("preferred_state")
        city = cleaned.get("preferred_city")
        if city and state and city.state_id != state.pk:
            self.add_error("preferred_city", "Choose a city within the selected state.")
        if city and not state:
            cleaned["preferred_state"] = city.state
        return cleaned


class CandidatePrivacyForm(StyledFormMixin, forms.Form):
    is_open_to_work = forms.BooleanField(
        label="Show recruiters that I am open to opportunities",
        required=False,
    )
    share_profile_with_recruiters = forms.BooleanField(
        label="Share my academic profile with recruiters when I apply",
        required=False,
        help_text="Turning this off hides your profile details from recruiters, but your application record remains.",
    )
    marketing = forms.BooleanField(
        label="Send me career resources and FacultyNxtGen updates",
        required=False,
    )

    def __init__(self, *args, profile=None, preference=None, **kwargs):
        self.profile = profile
        self.preference = preference
        initial = kwargs.setdefault("initial", {})
        if profile:
            initial.update(
                {
                    "is_open_to_work": profile.is_open_to_work,
                    "share_profile_with_recruiters": profile.share_profile_with_recruiters,
                }
            )
        if preference:
            initial["marketing"] = preference.marketing
        super().__init__(*args, **kwargs)

    def save(self):
        self.profile.is_open_to_work = self.cleaned_data["is_open_to_work"]
        self.profile.share_profile_with_recruiters = self.cleaned_data[
            "share_profile_with_recruiters"
        ]
        self.profile.save(
            update_fields=["is_open_to_work", "share_profile_with_recruiters", "updated_at"]
        )
        self.preference.marketing = self.cleaned_data["marketing"]
        self.preference.save(update_fields=["marketing", "updated_at"])
        return self.profile


class QualificationForm(StyledFormMixin, forms.ModelForm):
    document_file = forms.FileField(
        label="Certificate (optional)",
        required=False,
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="PDF, JPG or PNG up to 5 MB.",
    )

    class Meta:
        model = Qualification
        fields = [
            "level",
            "degree",
            "specialization",
            "institution",
            "university_board",
            "year_completed",
            "percentage_or_grade",
        ]
        widgets = {
            "degree": forms.TextInput(attrs={"placeholder": "Example: M.Sc. Physics"}),
            "specialization": forms.TextInput(attrs={"placeholder": "Example: Condensed Matter Physics"}),
            "institution": forms.TextInput(attrs={"placeholder": "College or university name"}),
            "university_board": forms.TextInput(attrs={"placeholder": "Affiliating university or board"}),
            "year_completed": forms.NumberInput(attrs={"min": 1950, "max": 2035}),
            "percentage_or_grade": forms.TextInput(attrs={"placeholder": "Example: 78% or 8.4 CGPA"}),
        }


class TeachingExperienceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TeachingExperience
        fields = [
            "designation",
            "institution",
            "department",
            "start_date",
            "end_date",
            "is_current",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "is_current": forms.CheckboxInput(attrs={"data-current-role": ""}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "designation": forms.TextInput(attrs={"placeholder": "Example: Assistant Professor"}),
            "institution": forms.TextInput(attrs={"placeholder": "Institution name"}),
            "department": forms.TextInput(attrs={"placeholder": "Department"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_current"):
            cleaned["end_date"] = None
        return cleaned


class ResearchExperienceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ResearchExperience
        fields = [
            "role",
            "institution",
            "research_area",
            "funding_agency",
            "start_date",
            "end_date",
            "is_current",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "is_current": forms.CheckboxInput(attrs={"data-current-role": ""}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "role": forms.TextInput(attrs={"placeholder": "Example: Junior Research Fellow"}),
            "institution": forms.TextInput(attrs={"placeholder": "Institution or laboratory"}),
            "research_area": forms.TextInput(attrs={"placeholder": "Research area"}),
            "funding_agency": forms.TextInput(attrs={"placeholder": "Funding agency, if any"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_current"):
            cleaned["end_date"] = None
        return cleaned


class PublicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Publication
        fields = [
            "title",
            "authors",
            "venue",
            "publication_type",
            "year",
            "doi",
            "url",
            "indexing",
            "is_peer_reviewed",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Full publication title"}),
            "authors": forms.TextInput(attrs={"placeholder": "Author 1, Author 2, Author 3"}),
            "venue": forms.TextInput(attrs={"placeholder": "Journal or conference name"}),
            "year": forms.NumberInput(attrs={"min": 1950}),
            "doi": forms.TextInput(attrs={"placeholder": "10.xxxx/xxxxx"}),
            "indexing": forms.TextInput(attrs={"placeholder": "Scopus, Web of Science, UGC CARE"}),
        }


class CertificationForm(StyledFormMixin, forms.ModelForm):
    document_file = forms.FileField(
        label="Certificate file (optional)",
        required=False,
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="PDF, JPG or PNG up to 5 MB.",
    )

    class Meta:
        model = Certification
        fields = [
            "name",
            "issuing_organization",
            "issue_date",
            "expiry_date",
            "credential_url",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Certification name"}),
            "issuing_organization": forms.TextInput(attrs={"placeholder": "Issuing organisation"}),
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "credential_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("issue_date") and cleaned.get("expiry_date") and cleaned["expiry_date"] < cleaned["issue_date"]:
            self.add_error("expiry_date", "Expiry date cannot be before the issue date.")
        return cleaned


class CandidateDocumentUploadForm(StyledFormMixin, forms.Form):
    purpose = forms.ChoiceField(
        label="Document type",
        choices=[
            (Document.Purpose.CV, "CV / Resume"),
            (Document.Purpose.CERTIFICATE, "Certificate or supporting document"),
        ],
    )
    file = forms.FileField(
        label="Choose file",
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="PDF preferred. JPG or PNG accepted. Maximum 5 MB.",
    )
    description = forms.CharField(
        label="Short label (optional)",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Example: Updated CV — November 2026"}),
    )

    def clean_file(self):
        from apps.documents.models import scan_for_malware
        from apps.core.utils import validate_uploaded_document

        uploaded = self.cleaned_data["file"]
        validate_uploaded_document(uploaded)
        if not scan_for_malware(uploaded):
            raise ValidationError("This file could not be scanned and was not uploaded.")
        return uploaded
