from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import MultipleFileField, MultipleFileInput, StyledFormMixin
from apps.core.utils import validate_uploaded_document

from .models import Application


class ApplicationForm(StyledFormMixin, forms.Form):
    cover_letter = forms.CharField(
        label="Cover letter",
        required=False,
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Optional. Explain your suitability for this specific vacancy.",
            }
        ),
        help_text="Do not include sensitive personal data such as caste, religion, marital status or photographs unless the official notification requires it.",
    )
    resume = forms.FileField(
        label="Upload a fresh CV (optional)",
        required=False,
        widget=forms.FileInput(attrs={"accept": "application/pdf,image/jpeg,image/png"}),
        help_text="If left blank, we use the CV saved in your profile.",
    )
    attachments = MultipleFileField(
        label="Supporting documents (optional)",
        required=False,
        widget=MultipleFileInput(
            attrs={
                "accept": "application/pdf,image/jpeg,image/png",
                "data-max-files": "5",
            }
        ),
        help_text="Degree certificates, NET/SET scorecards, experience letters. Up to 5 files, 5 MB each.",
    )
    consent = forms.BooleanField(
        label="I allow the institution to review my academic profile and documents for this application",
        error_messages={"required": "Consent is required to submit an application."},
    )

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        if not (profile and profile.cv_id and not profile.cv.is_deleted):
            self.fields["resume"].required = False
            self.fields["resume"].help_text = (
                "Upload your CV. It remains private and is shared only with this institution."
            )

    def clean_resume(self):
        file = self.cleaned_data.get("resume")
        if file:
            validate_uploaded_document(file)
        return file

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("resume") and not (
            self.profile and self.profile.cv_id and not self.profile.cv.is_deleted
        ):
            self.add_error("resume", "Upload a CV to apply.")
        attachments = self.files.getlist("attachments") if hasattr(self, "files") else []
        if len(attachments) > 5:
            self.add_error("attachments", "Attach no more than 5 supporting documents.")
        for attachment in attachments:
            try:
                validate_uploaded_document(attachment)
            except ValidationError as exc:
                self.add_error("attachments", exc)
            if attachment.size > 5 * 1024 * 1024:
                self.add_error("attachments", f"{attachment.name} is larger than 5 MB.")
        return cleaned


class ApplicationStatusForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(
        choices=[
            (Application.Status.UNDER_REVIEW, "Move to under review"),
            (Application.Status.SHORTLISTED, "Shortlist candidate"),
            (Application.Status.SELECTED, "Mark as selected"),
            (Application.Status.REJECTED, "Not selected"),
        ]
    )
    note = forms.CharField(
        label="Message to the candidate (optional)",
        required=False,
        max_length=2000,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "This message is visible to the candidate."}
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == Application.Status.REJECTED and not (cleaned.get("note") or "").strip():
            self.add_error("note", "Add a brief, constructive reason that will be shared with the candidate.")
        return cleaned


class ApplicationNoteForm(StyledFormMixin, forms.Form):
    note = forms.CharField(
        label="Internal note",
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Visible only to your institution's recruitment team.",
            }
        ),
    )
