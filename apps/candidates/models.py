import uuid
from datetime import date

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.constants import DEGREE_LEVELS, PH_D_STATUSES
from apps.core.validators import validate_image_file

from .utils import validate_image


class CandidateProfile(models.Model):
    class PhDStatus(models.TextChoices):
        COMPLETED = "completed", "PhD completed"
        PURSUING = "pursuing", "PhD pursuing"
        AWARDED = "awarded", "PhD awarded"
        NOT_STARTED = "not_started", "Not started"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    headline = models.CharField(
        max_length=180,
        blank=True,
        help_text="Example: Assistant Professor · Computer Science · PhD (Pursuing)",
    )
    bio = models.TextField(max_length=3000, blank=True)
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        validators=[validate_image],
        help_text="Optional. JPG, PNG or WEBP up to 2 MB.",
    )
    highest_qualification = models.CharField(max_length=120, blank=True)
    ug_degree = models.CharField("UG degree", max_length=180, blank=True)
    pg_degree = models.CharField("PG degree", max_length=180, blank=True)
    phd_status = models.CharField(
        max_length=20, choices=PhDStatus.choices, default=PhDStatus.NOT_STARTED
    )
    phd_thesis_title = models.CharField(max_length=300, blank=True)
    specialization = models.CharField(max_length=180, blank=True)
    department = models.ForeignKey(
        "jobs.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_profiles",
    )
    teaching_experience_years = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(50)]
    )
    research_experience_years = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(50)]
    )
    current_designation = models.CharField(max_length=150, blank=True)
    current_institution = models.CharField(max_length=220, blank=True)
    preferred_state = models.ForeignKey(
        "core.State",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_preferences",
    )
    preferred_city = models.ForeignKey(
        "core.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_preferences",
    )
    preferred_designation = models.ForeignKey(
        "jobs.Designation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_preferences",
    )
    preferred_employment_type = models.CharField(max_length=20, blank=True)
    is_open_to_work = models.BooleanField(default=True)
    share_profile_with_recruiters = models.BooleanField(
        default=True,
        help_text="Your profile is only shared with recruiters when you apply to their vacancy.",
    )
    cv = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_cv_for",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "candidate profile"

    def __str__(self):
        return f"{self.user.get_full_name()} — candidate profile"

    @property
    def completion_percentage(self):
        checks = [
            (self.headline, 8),
            (self.bio, 7),
            (self.highest_qualification, 10),
            (self.specialization, 8),
            (self.department_id, 8),
            (self.preferred_designation_id, 5),
            (self.preferred_state_id, 5),
            (self.ug_degree, 5),
            (self.pg_degree, 7),
            (self.phd_status != self.PhDStatus.NOT_STARTED, 5),
            (self.teaching_experience_years or self.research_experience_years, 5),
            (self.qualifications.exists(), 10),
            (self.cv_id and not self.cv.is_deleted, 12),
            (self.avatar, 5),
        ]
        earned = sum(weight for value, weight in checks if value)
        return min(100, earned)

    @property
    def preferred_location_display(self):
        if self.preferred_city:
            return f"{self.preferred_city.name}, {self.preferred_city.state.name}"
        if self.preferred_state:
            return self.preferred_state.name
        return "Open to opportunities"

    @property
    def years_experience(self):
        return max(self.teaching_experience_years, self.research_experience_years)

    def get_absolute_url(self):
        return reverse("candidates:dashboard")


class Qualification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="qualifications"
    )
    level = models.CharField(max_length=20, choices=DEGREE_LEVELS)
    degree = models.CharField(max_length=180)
    specialization = models.CharField(max_length=180, blank=True)
    institution = models.CharField(max_length=220)
    university_board = models.CharField(max_length=220, blank=True)
    year_completed = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1950),
            MaxValueValidator(date.today().year + 8),
        ]
    )
    percentage_or_grade = models.CharField(max_length=40, blank=True)
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qualifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year_completed", "-created_at"]

    def __str__(self):
        return f"{self.degree} ({self.year_completed})"


class TeachingExperience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="teaching_experiences"
    )
    designation = models.CharField(max_length=150)
    institution = models.CharField(max_length=220)
    department = models.CharField(max_length=150, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_current", "-start_date"]

    def __str__(self):
        return f"{self.designation} at {self.institution}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.is_current and self.end_date:
            raise ValidationError({"end_date": "Leave end date blank for a current role."})
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})
        if self.start_date and self.start_date > timezone.localdate():
            raise ValidationError({"start_date": "Start date cannot be in the future."})

    @property
    def duration_label(self):
        end = "Present" if self.is_current or not self.end_date else self.end_date.strftime("%b %Y")
        return f"{self.start_date.strftime('%b %Y')} – {end}"


class ResearchExperience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="research_experiences"
    )
    role = models.CharField(max_length=180)
    institution = models.CharField(max_length=220)
    research_area = models.CharField(max_length=220, blank=True)
    funding_agency = models.CharField(max_length=220, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_current", "-start_date"]
        verbose_name_plural = "research experience"

    def __str__(self):
        return f"{self.role} at {self.institution}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.is_current and self.end_date:
            raise ValidationError({"end_date": "Leave end date blank for a current role."})
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    @property
    def duration_label(self):
        end = "Present" if self.is_current or not self.end_date else self.end_date.strftime("%b %Y")
        return f"{self.start_date.strftime('%b %Y')} – {end}"


class Publication(models.Model):
    class Type(models.TextChoices):
        JOURNAL = "journal", "Journal article"
        CONFERENCE = "conference", "Conference paper"
        BOOK = "book", "Book"
        CHAPTER = "chapter", "Book chapter"
        PATENT = "patent", "Patent"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="publications"
    )
    title = models.CharField(max_length=400)
    authors = models.CharField(max_length=500, help_text="List authors as they appear in the publication.")
    venue = models.CharField(
        max_length=300, help_text="Journal, conference, book or publisher."
    )
    publication_type = models.CharField(max_length=20, choices=Type.choices, default=Type.JOURNAL)
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(date.today().year + 2)]
    )
    doi = models.CharField(max_length=150, blank=True)
    url = models.URLField(blank=True, max_length=500)
    indexing = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: Scopus, Web of Science, UGC CARE.",
    )
    is_peer_reviewed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-created_at"]

    def __str__(self):
        return self.title


class Certification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="certifications"
    )
    name = models.CharField(max_length=240)
    issuing_organization = models.CharField(max_length=220)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    credential_url = models.URLField(blank=True, max_length=500)
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return self.name
