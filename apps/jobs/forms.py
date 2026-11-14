from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.constants import EMPLOYMENT_TYPES
from apps.core.forms import StyledFormMixin
from apps.core.models import City, State
from apps.core.widgets import CitySelect
from apps.documents.models import Document, scan_for_malware
from apps.core.utils import validate_uploaded_document

from .models import Department, Designation, Job, JobAlert, JobReport


class JobForm(StyledFormMixin, forms.ModelForm):
    notification_file = forms.FileField(
        label="Original recruitment notification",
        required=False,
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="PDF up to 5 MB. Published privately and shown to candidates for this vacancy.",
    )
    authorization_confirmed = forms.BooleanField(
        label="I confirm I am authorised by the institution to publish this vacancy",
        required=False,
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "designation",
            "department",
            "specialization",
            "employment_type",
            "vacancies",
            "state",
            "city",
            "campus_location",
            "required_qualification",
            "experience_min",
            "experience_max",
            "salary_disclosed",
            "salary_min",
            "salary_max",
            "salary_period",
            "salary_notes",
            "description",
            "eligibility",
            "required_documents",
            "application_method",
            "application_instruction",
            "external_application_url",
            "external_application_email",
            "deadline",
            "publication_date",
            "notification_url",
            "source_information",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Example: Assistant Professor — Computer Science"}
            ),
            "specialization": forms.TextInput(
                attrs={"placeholder": "Example: Artificial Intelligence, Data Science"}
            ),
            "campus_location": forms.TextInput(attrs={"placeholder": "Main campus, city area"}),
            "required_qualification": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Example: PhD in Computer Science; UGC-NET qualified."}
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": "Describe the role, department context and responsibilities.",
                }
            ),
            "eligibility": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Eligibility conditions as per the official notification."}
            ),
            "required_documents": forms.Textarea(
                attrs={"rows": 4, "placeholder": "One document per line, e.g.\nUpdated CV\nPhD certificate\nUGC-NET scorecard"}
            ),
            "application_instruction": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Explain the application procedure, fees and submission details."}
            ),
            "source_information": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Official notification number, source and date.",
                }
            ),
            "external_application_url": forms.URLInput(attrs={"placeholder": "https://institution.ac.in/careers"}),
            "external_application_email": forms.EmailInput(attrs={"placeholder": "recruitment@institution.ac.in"}),
            "salary_notes": forms.TextInput(
                attrs={"placeholder": "Example: UGC pay matrix, Level 10 with allowances."}
            ),
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "publication_date": forms.DateInput(attrs={"type": "date"}),
            "notification_url": forms.URLInput(attrs={"placeholder": "https://institution.ac.in/notification.pdf"}),
            "vacancies": forms.NumberInput(attrs={"min": 1}),
            "experience_min": forms.NumberInput(attrs={"min": 0, "max": 40}),
            "experience_max": forms.NumberInput(attrs={"min": 0, "max": 40}),
            "salary_min": forms.NumberInput(attrs={"min": 0, "step": "1000"}),
            "salary_max": forms.NumberInput(attrs={"min": 0, "step": "1000"}),
            "state": forms.Select(
                attrs={"data-state-select": "", "data-city-target": "#id_city"}
            ),
            "salary_disclosed": forms.CheckboxInput(
                attrs={"data-toggle-target": "#salary-fields"}
            ),
            "application_method": forms.Select(
                attrs={
                    "data-toggle-target": "#external-application-fields",
                    "data-toggle-value": "external",
                }
            ),
            "city": CitySelect(),
        }
        help_texts = {
            "publication_date": "Date of the official advertisement. Defaults to today.",
            "deadline": "The last date candidates can apply.",
            "external_application_url": "Official institution page or application portal.",
            "external_application_email": "Official recruitment email address.",
            "notification_url": "Link to the original PDF or notice on the institution website.",
            "source_information": "Required: reference number or source that lets our team verify the vacancy.",
        }
        labels = {
            "required_qualification": "Required qualifications",
            "notification_file": "Recruitment notification",
        }

    def __init__(self, *args, action="draft", institution=None, user=None, **kwargs):
        self.action = action
        self.institution = institution
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["designation"].queryset = Designation.objects.filter(is_active=True)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["state"].queryset = State.objects.filter(is_active=True)
        self.fields["city"].queryset = City.objects.filter(is_active=True).select_related("state")
        for field in self.fields.values():
            field.required = False
        self.fields["employment_type"].choices = EMPLOYMENT_TYPES
        self.fields["application_method"].choices = Job.ApplicationMethod.choices
        # Structural fields are needed even to save a meaningful draft.
        for name in [
            "title",
            "designation",
            "department",
            "state",
            "city",
            "employment_type",
            "application_method",
            "publication_date",
        ]:
            self.fields[name].required = True
        if not self.instance.pk:
            self.fields["publication_date"].initial = timezone.localdate()

        if action == "submit":
            for name in [
                "title",
                "designation",
                "department",
                "state",
                "city",
                "employment_type",
                "required_qualification",
                "description",
                "eligibility",
                "application_method",
                "deadline",
                "publication_date",
                "source_information",
            ]:
                self.fields[name].required = True
            self.fields["authorization_confirmed"].required = True
        if action == "submit":
            self.fields["authorization_confirmed"].widget.attrs["required"] = True

    def clean(self):
        cleaned = super().clean()
        state = cleaned.get("state")
        city = cleaned.get("city")
        if city and state and city.state_id != state.pk:
            self.add_error("city", "Choose a city within the selected state.")
        if city and not state:
            cleaned["state"] = city.state
        minimum = cleaned.get("experience_min")
        maximum = cleaned.get("experience_max")
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error("experience_max", "Maximum experience cannot be less than minimum.")
        if cleaned.get("salary_disclosed"):
            if cleaned.get("salary_min") is None and cleaned.get("salary_max") is None:
                self.add_error("salary_min", "Enter a salary range or untick salary disclosure.")
            if (
                cleaned.get("salary_min") is not None
                and cleaned.get("salary_max") is not None
                and cleaned["salary_max"] < cleaned["salary_min"]
            ):
                self.add_error("salary_max", "Maximum salary cannot be less than minimum.")
        if (
            cleaned.get("application_method") == Job.ApplicationMethod.EXTERNAL
            and not cleaned.get("external_application_url")
            and not cleaned.get("external_application_email")
        ):
            self.add_error(
                "external_application_url",
                "Add the official application URL or recruitment email.",
            )
        deadline = cleaned.get("deadline")
        publication = cleaned.get("publication_date")
        if self.action == "submit":
            if cleaned.get("application_method") == Job.ApplicationMethod.INTERNAL and cleaned.get("external_application_url"):
                pass
            if deadline and deadline < timezone.localdate():
                self.add_error("deadline", "The deadline must be today or later.")
            if deadline and publication and deadline < publication:
                self.add_error("deadline", "The deadline cannot be before the publication date.")
            if not cleaned.get("notification_file") and not cleaned.get("notification_url"):
                if not (self.instance.pk and self.instance.notification_document_id):
                    self.add_error(
                        "notification_file",
                        "Attach the original notification or provide its official URL.",
                    )
            if not cleaned.get("source_information"):
                self.add_error("source_information", "Add the official reference or source details.")
        if cleaned.get("external_application_url"):
            url = cleaned["external_application_url"]
            if not url.startswith(("http://", "https://")):
                self.add_error("external_application_url", "Use a complete http:// or https:// URL.")
        return cleaned

    def clean_notification_file(self):
        file = self.cleaned_data.get("notification_file")
        if file:
            validate_uploaded_document(file)
            if not scan_for_malware(file):
                raise ValidationError("This file could not be scanned and was not uploaded.")
        return file


class JobAlertForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = JobAlert
        fields = [
            "name",
            "keyword",
            "department",
            "designation",
            "state",
            "city",
            "employment_type",
            "frequency",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Example: Assistant Professor — Physics"}),
            "keyword": forms.TextInput(attrs={"placeholder": "Optional keyword, department or institution"}),
            "employment_type": forms.Select(choices=[("", "Any employment type")] + EMPLOYMENT_TYPES),
            "state": forms.Select(
                attrs={"data-state-select": "", "data-city-target": "#id_city"}
            ),
            "city": CitySelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["designation"].queryset = Designation.objects.filter(is_active=True)
        self.fields["state"].queryset = State.objects.filter(is_active=True)
        self.fields["city"].queryset = City.objects.filter(is_active=True).select_related("state")
        for name in ("department", "designation", "state", "city", "employment_type", "keyword"):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("city") and cleaned.get("state") and cleaned["city"].state_id != cleaned["state"].pk:
            self.add_error("city", "Choose a city within the selected state.")
        if cleaned.get("city") and not cleaned.get("state"):
            cleaned["state"] = cleaned["city"].state
        if not any(
            [
                cleaned.get("keyword"),
                cleaned.get("department"),
                cleaned.get("designation"),
                cleaned.get("state"),
                cleaned.get("city"),
                cleaned.get("employment_type"),
            ]
        ):
            raise ValidationError("Choose at least one matching criterion for the alert.")
        return cleaned


class JobReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = JobReport
        fields = ["reason", "details"]
        widgets = {
            "details": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Tell us what looks wrong. Include details our verification team can check."}
            ),
        }
        labels = {"details": "What should we check?"}

    def clean_details(self):
        details = self.cleaned_data["details"].strip()
        if len(details) < 20:
            raise ValidationError("Please add enough detail for our team to investigate (at least 20 characters).")
        return details


class JobReviewForm(forms.Form):
    verified_institution = forms.BooleanField(
        label="Institution identity and verification are current",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    verified_recruiter = forms.BooleanField(
        label="Recruiter is authorised to publish for this institution",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    verified_advertisement = forms.BooleanField(
        label="Vacancy is authentic and matches the official notification",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    verified_application_url = forms.BooleanField(
        label="Application URL or email is official and reachable",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    verified_deadline = forms.BooleanField(
        label="Application deadline is correct",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    verified_eligibility = forms.BooleanField(
        label="Eligibility and required documents are complete",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    review_notes = forms.CharField(
        label="Internal review notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )

    def __init__(self, *args, action="review", **kwargs):
        self.action = action
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        checklist = [
            "verified_institution",
            "verified_recruiter",
            "verified_advertisement",
            "verified_application_url",
            "verified_deadline",
            "verified_eligibility",
        ]
        if self.action == "publish" and not all(cleaned.get(name) for name in checklist):
            raise ValidationError("Every verification checkbox must be completed before publishing.")
        return cleaned


class JobRejectForm(forms.Form):
    reason = forms.CharField(
        label="Reason shared with the institution",
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "form-control", "placeholder": "Explain what must be corrected before resubmission."}
        ),
        min_length=15,
    )


class JobSuspendForm(forms.Form):
    reason = forms.CharField(
        label="Reason for suspension",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        min_length=10,
    )
