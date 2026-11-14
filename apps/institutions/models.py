import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import INSTITUTION_TYPES
from apps.core.validators import validate_image_file
from apps.core.utils import institution_logo_upload_to


class Institution(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=240, unique=True)
    slug = models.SlugField(max_length=260, unique=True, blank=True)
    website = models.URLField(max_length=500)
    official_email = models.EmailField()
    phone = models.CharField(max_length=25)
    contact_person = models.CharField(max_length=150)
    contact_designation = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=25, blank=True)
    contact_email = models.EmailField(blank=True)
    address = models.TextField(max_length=1000)
    state = models.ForeignKey("core.State", on_delete=models.PROTECT, related_name="institutions")
    city = models.ForeignKey("core.City", on_delete=models.PROTECT, related_name="institutions")
    pincode = models.CharField(max_length=10, blank=True)
    institution_type = models.CharField(max_length=30, choices=INSTITUTION_TYPES)
    description = models.TextField(max_length=6000, blank=True)
    established_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1800), MaxValueValidator(timezone.localdate().year)],
    )
    logo = models.ImageField(
        upload_to=institution_logo_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_notes = models.TextField(
        blank=True, help_text="Internal notes from the verification team."
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_institutions",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["verification_status", "is_active"]),
            models.Index(fields=["state", "city"]),
            models.Index(fields=["institution_type"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:240]
            candidate = base
            counter = 2
            while Institution.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def verification_label(self):
        return {
            "verified": "Verified institution",
            "pending": "Verification pending",
            "rejected": "Verification not approved",
            "suspended": "Institution suspended",
        }.get(self.verification_status, "Verification pending")

    @property
    def is_verified(self):
        return self.verification_status == self.VerificationStatus.VERIFIED and self.is_active

    def get_absolute_url(self):
        return reverse("institutions:detail", args=[self.slug])


class InstitutionDocument(models.Model):
    class DocType(models.TextChoices):
        AUTHORIZATION = "authorization", "Authorisation letter"
        REGISTRATION = "registration", "Registration certificate"
        AFFILIATION = "affiliation", "Affiliation certificate"
        OTHER = "other", "Other official document"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="verification_documents"
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="institution_documents",
    )
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_institution_documents"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.institution.name}"


class Recruiter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruiter_profile",
    )
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="recruiters"
    )
    designation = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=25, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_recruiters",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution"],
                condition=models.Q(is_primary=True),
                name="one_primary_recruiter_per_institution",
            )
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.institution.name}"

    @property
    def is_verified_for_institution(self):
        return self.is_active and self.institution.is_verified

    def can_manage(self):
        return self.is_active and self.institution.is_active


def institution_for_user(user):
    """Safe institution lookup for recruiter users."""
    if not user.is_authenticated or not user.is_recruiter:
        return None
    recruiter = (
        Recruiter.objects.select_related("institution")
        .filter(user=user, is_active=True, institution__is_active=True)
        .first()
    )
    return recruiter.institution if recruiter else None
