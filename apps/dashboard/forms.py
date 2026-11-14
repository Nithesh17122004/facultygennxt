from django import forms

from apps.institutions.models import Institution


class InstitutionDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        label="Decision",
        choices=[
            (Institution.VerificationStatus.VERIFIED, "Verify institution"),
            (Institution.VerificationStatus.REJECTED, "Reject verification"),
            (Institution.VerificationStatus.SUSPENDED, "Suspend institution"),
            (Institution.VerificationStatus.PENDING, "Return to pending review"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        label="Review notes",
        required=False,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": "Explain the decision. This is shared with the institution for rejections and suspensions.",
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get("decision")
        notes = (cleaned.get("notes") or "").strip()
        if decision in {
            Institution.VerificationStatus.REJECTED,
            Institution.VerificationStatus.SUSPENDED,
        } and len(notes) < 10:
            self.add_error("notes", "Add a clear reason (at least 10 characters).")
        cleaned["notes"] = notes
        return cleaned


class ReportResolutionForm(forms.Form):
    status = forms.ChoiceField(
        label="Resolution",
        choices=[("resolved", "Resolved"), ("dismissed", "Dismissed"), ("investigating", "Mark investigating")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resolution_notes = forms.CharField(
        label="Resolution notes",
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )
    suspend_job = forms.BooleanField(
        label="Suspend the reported vacancy while this report is resolved",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class UserModerationForm(forms.Form):
    ACTION_CHOICES = [
        ("activate", "Activate account"),
        ("deactivate", "Deactivate account"),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    notes = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Internal note",
    )


class ContentNoteForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            ("new", "New"),
            ("in_progress", "In progress"),
            ("resolved", "Resolved"),
            ("spam", "Spam"),
        ]
    )
    admin_notes = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
