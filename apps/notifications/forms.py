from django import forms

from .models import EmailPreference


class EmailPreferenceForm(forms.ModelForm):
    class Meta:
        model = EmailPreference
        fields = ["job_alerts", "application_updates", "institution_updates", "marketing"]
        labels = {
            "job_alerts": "Job alert emails",
            "application_updates": "Application status updates",
            "institution_updates": "Institution and recruiter updates",
            "marketing": "Career resources and FacultyNxtGen product news",
        }
        widgets = {
            "job_alerts": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "application_updates": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "institution_updates": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "marketing": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "job_alerts": "Only alerts you create yourself. You can unsubscribe at any time.",
            "marketing": "Optional. Off by default, in line with India's DPDP framework.",
        }
