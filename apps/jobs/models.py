import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import EMPLOYMENT_TYPES, EMPLOYMENT_TYPE_NAMES
from apps.core.utils import random_upload_to, validate_uploaded_document

from .managers import JobQuerySet


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.CharField(max_length=300, blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Bootstrap Icons class, e.g. bi-cpu. Optional.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Designation(models.Model):
    class Category(models.TextChoices):
        TEACHING = "teaching", "Teaching"
        RESEARCH = "research", "Research"
        NON_TEACHING = "non_teaching", "Non-teaching"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.TEACHING)
    description = models.CharField(max_length=300, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Job(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        SUSPENDED = "suspended", "Suspended"

    class ApplicationMethod(models.TextChoices):
        EXTERNAL = "external", "External institution application"
        INTERNAL = "internal", "Through FacultyNxtGen"

    class SalaryPeriod(models.TextChoices):
        MONTH = "month", "Per month"
        YEAR = "year", "Per annum"
        CONSOLIDATED = "consolidated", "Consolidated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=260, unique=True, blank=True)
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.CASCADE, related_name="jobs"
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_jobs",
    )
    title = models.CharField(max_length=240)
    designation = models.ForeignKey(
        Designation, on_delete=models.PROTECT, related_name="jobs"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="jobs"
    )
    specialization = models.CharField(max_length=220, blank=True)
    state = models.ForeignKey("core.State", on_delete=models.PROTECT, related_name="jobs")
    city = models.ForeignKey("core.City", on_delete=models.PROTECT, related_name="jobs")
    campus_location = models.CharField(
        max_length=220, blank=True, help_text="Campus, street or area (optional)."
    )
    employment_type = models.CharField(
        max_length=20, choices=EMPLOYMENT_TYPES, default="full_time"
    )
    vacancies = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    required_qualification = models.TextField(
        max_length=3000,
        blank=True,
        help_text="Minimum degree, NET/SET/PhD requirements and any equivalence conditions.",
    )
    experience_min = models.PositiveSmallIntegerField(default=0)
    experience_max = models.PositiveSmallIntegerField(null=True, blank=True)
    salary_disclosed = models.BooleanField(default=False)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_period = models.CharField(
        max_length=20, choices=SalaryPeriod.choices, default=SalaryPeriod.MONTH
    )
    salary_notes = models.CharField(
        max_length=300, blank=True, help_text="Example: As per UGC pay matrix, Level 10."
    )
    description = models.TextField(max_length=12000, blank=True)
    eligibility = models.TextField(max_length=6000, blank=True)
    required_documents = models.TextField(
        max_length=3000, blank=True, help_text="List one required document per line."
    )
    application_instruction = models.TextField(
        max_length=3000, blank=True, help_text="How candidates should apply."
    )
    application_method = models.CharField(
        max_length=20, choices=ApplicationMethod.choices, default=ApplicationMethod.EXTERNAL
    )
    external_application_url = models.URLField(max_length=600, blank=True)
    external_application_email = models.EmailField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    publication_date = models.DateField(default=timezone.localdate)
    notification_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_for_jobs",
        help_text="Original recruitment notification, if available.",
    )
    notification_url = models.URLField(
        max_length=600, blank=True, help_text="Official notification URL, if published online."
    )
    source_information = models.TextField(
        max_length=3000,
        blank=True,
        help_text="Where the vacancy was announced and any official reference number.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    rejection_reason = models.TextField(blank=True)
    suspension_reason = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_jobs",
    )
    review_notes = models.TextField(blank=True)
    is_platform_posted = models.BooleanField(default=False)
    verified_institution = models.BooleanField(default=False)
    verified_recruiter = models.BooleanField(default=False)
    verified_advertisement = models.BooleanField(default=False)
    verified_application_url = models.BooleanField(default=False)
    verified_deadline = models.BooleanField(default=False)
    verified_eligibility = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    expiry_notified_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "deadline"]),
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["state", "city"]),
            models.Index(fields=["designation", "department"]),
            models.Index(fields=["institution", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(experience_max__isnull=True) | Q(experience_max__gte=models.F("experience_min")),
                name="job_experience_max_gte_min",
            ),
            models.CheckConstraint(
                condition=Q(deadline__isnull=True) | Q(deadline__gte=models.F("publication_date")),
                name="job_deadline_after_publication",
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.institution.name}"

    def clean(self):
        errors = {}
        if self.city_id and self.state_id and self.city.state_id != self.state_id:
            errors["city"] = "The city must be in the selected state."
        if self.experience_max is not None and self.experience_max < self.experience_min:
            errors["experience_max"] = "Maximum experience cannot be less than minimum experience."
        if self.salary_disclosed:
            if self.salary_min is None and self.salary_max is None:
                errors["salary_min"] = "Disclose a salary range or mark salary as not disclosed."
            if self.salary_min is not None and self.salary_max is not None and self.salary_max < self.salary_min:
                errors["salary_max"] = "Maximum salary cannot be less than minimum salary."
        if self.application_method == self.ApplicationMethod.EXTERNAL:
            if not self.external_application_url and not self.external_application_email:
                errors["external_application_url"] = "Add an official application URL or email address."
        if self.deadline and self.deadline < self.publication_date:
            errors["deadline"] = "The deadline cannot be before the publication date."
        if errors:
            raise ValidationError(errors)

    @property
    def is_live(self):
        return (
            self.status == self.Status.PUBLISHED
            and not self.is_deleted
            and self.deadline is not None
            and self.deadline >= timezone.localdate()
            and self.institution.verification_status == "verified"
        )

    @property
    def is_expired(self):
        return self.status == self.Status.EXPIRED or (
            self.deadline is not None and self.deadline < timezone.localdate()
        )

    @property
    def days_left(self):
        if not self.deadline:
            return None
        return (self.deadline - timezone.localdate()).days

    @property
    def deadline_label(self):
        if not self.deadline:
            return "Not specified"
        days = self.days_left
        if days is None:
            return "Not specified"
        if days < 0:
            return "Closed"
        if days == 0:
            return "Closes today"
        if days == 1:
            return "1 day left"
        return f"{days} days left"

    @property
    def verification_checklist_complete(self):
        return all(
            [
                self.verified_institution,
                self.verified_recruiter,
                self.verified_advertisement,
                self.verified_application_url,
                self.verified_deadline,
                self.verified_eligibility,
            ]
        )

    @property
    def salary_is_disclosed(self):
        return bool(self.salary_disclosed and (self.salary_min or self.salary_max))

    @property
    def employment_type_label(self):
        return EMPLOYMENT_TYPE_NAMES.get(self.employment_type, self.get_employment_type_display())

    @property
    def location_label(self):
        return f"{self.city.name}, {self.state.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.title} {self.institution.name}")[:220] or f"faculty-vacancy-{self.pk}"
            candidate = base
            counter = 2
            while Job.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("jobs:detail", args=[self.slug])

    def can_edit(self):
        return self.status in {self.Status.DRAFT, self.Status.REJECTED}

    def can_delete(self):
        return self.status in {self.Status.DRAFT, self.Status.REJECTED}

    def external_apply_link(self):
        return self.external_application_url or (
            f"mailto:{self.external_application_email}" if self.external_application_email else ""
        )


class SavedJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_jobs"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "job"], name="unique_saved_job")
        ]

    def __str__(self):
        return f"{self.user.email} saved {self.job.title}"


class JobAlert(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily digest"
        WEEKLY = "weekly", "Weekly digest"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_alerts"
    )
    name = models.CharField(max_length=120)
    keyword = models.CharField(max_length=180, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )
    designation = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )
    state = models.ForeignKey(
        "core.State", on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )
    city = models.ForeignKey(
        "core.City", on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts"
    )
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, blank=True)
    frequency = models.CharField(
        max_length=10, choices=Frequency.choices, default=Frequency.WEEKLY
    )
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.user.email}"

    def matches(self, job):
        if self.keyword:
            needle = self.keyword.lower()
            haystack = " ".join(
                [
                    job.title,
                    job.specialization,
                    job.department.name,
                    job.designation.name,
                    job.institution.name,
                ]
            ).lower()
            if needle not in haystack:
                return False
        if self.department_id and job.department_id != self.department_id:
            return False
        if self.designation_id and job.designation_id != self.designation_id:
            return False
        if self.state_id and job.state_id != self.state_id:
            return False
        if self.city_id and job.city_id != self.city_id:
            return False
        if self.employment_type and job.employment_type != self.employment_type:
            return False
        return True


class JobReport(models.Model):
    class Reason(models.TextChoices):
        EXPIRED = "expired", "Deadline appears incorrect"
        MISLEADING = "misleading", "Misleading or incomplete information"
        DUPLICATE = "duplicate", "Duplicate vacancy"
        SUSPICIOUS = "suspicious", "Suspicious or fraudulent"
        WRONG_DETAILS = "wrong_details", "Incorrect institution or contact details"
        OTHER = "other", "Other concern"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        INVESTIGATING = "investigating", "Investigating"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="reports")
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_reports"
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    details = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_job_reports",
    )
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "reported_by"], name="unique_job_report_per_user")
        ]

    def __str__(self):
        return f"Report: {self.job.title}"


class JobStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "job status history"

    def __str__(self):
        return f"{self.job_id}: {self.from_status} → {self.to_status}"


class JobView(models.Model):
    """Deduplicated daily view count for recruiter analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="view_events")
    session_hash = models.CharField(max_length=64)
    viewed_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "session_hash", "viewed_on"],
                name="unique_job_view_per_session_day",
            )
        ]
        indexes = [models.Index(fields=["job", "viewed_on"])]
