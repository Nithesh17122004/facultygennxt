from django import forms

from .models import ContactEnquiry, NewsletterSubscriber


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return single_clean(data, initial)


class StyledFormMixin:
    """Adds consistent Bootstrap classes and accessible error attributes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            if css not in existing:
                widget.attrs["class"] = f"{existing} {css}".strip()
            if not field.required:
                widget.attrs.pop("required", None)

    def add_error(self, field, error):
        super().add_error(field, error)
        if field and field in self.fields:
            widget = self.fields[field].widget
            widget.attrs["aria-invalid"] = "true"
            classes = widget.attrs.get("class", "")
            if "is-invalid" not in classes:
                widget.attrs["class"] = f"{classes} is-invalid".strip()


class HoneypotMixin(StyledFormMixin):
    """A hidden field that catches simplistic bots without affecting users.

    The field is added in __init__ because plain Python mixins are not scanned
    by Django's form metaclass for declared fields.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["website"] = forms.CharField(
            required=False,
            widget=forms.HiddenInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
            label="",
        )

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("This form could not be submitted.")
        return value


class ContactForm(HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(
        label="I agree that FacultyNxtGen may use these details to respond to my enquiry",
        error_messages={"required": "Please confirm consent so we can respond."},
    )

    class Meta:
        model = ContactEnquiry
        fields = [
            "name",
            "email",
            "phone",
            "organization",
            "purpose",
            "subject",
            "message",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "organization": forms.TextInput(attrs={"placeholder": "Institution or organisation (optional)"}),
            "subject": forms.TextInput(attrs={"placeholder": "How can we help?"}),
            "message": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Share the details we need to help you. Do not include passwords or identity documents.",
                }
            ),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 20:
            raise forms.ValidationError("Please add enough detail for our team to help (at least 20 characters).")
        return message


class NewsletterForm(HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(
        label="I agree to receive occasional academic career resources and platform updates",
        error_messages={"required": "Please opt in to receive the newsletter."},
    )

    class Meta:
        model = NewsletterSubscriber
        fields = ["email", "name"]
        widgets = {
            "email": forms.EmailInput(
                attrs={"autocomplete": "email", "placeholder": "you@example.com"}
            ),
            "name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "First name (optional)"}
            ),
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
