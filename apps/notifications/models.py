from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Notification(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Action needed"

    class Category(models.TextChoices):
        ACCOUNT = "account", "Account"
        APPLICATION = "application", "Application"
        JOB = "job", "Jobs"
        INSTITUTION = "institution", "Institution"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField(max_length=2000)
    url = models.CharField(max_length=500, blank=True)
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.ACCOUNT
    )
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"])]

    def __str__(self):
        return f"{self.recipient.email}: {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class EmailPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_preferences",
    )
    job_alerts = models.BooleanField(
        default=True, help_text="Emails for alerts the candidate explicitly created."
    )
    application_updates = models.BooleanField(default=True)
    institution_updates = models.BooleanField(default=True)
    marketing = models.BooleanField(
        default=False,
        help_text="Product news and career resources. Requires explicit opt-in.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Email preferences — {self.user.email}"

    def allows(self, category):
        if category == "marketing":
            return self.marketing
        if category == "job_alert":
            return self.job_alerts
        if category == "application":
            return self.application_updates
        if category == "institution":
            return self.institution_updates
        return True


class EmailLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SUPPRESSED = "suppressed", "Suppressed by preferences"

    recipient_email = models.EmailField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    subject = models.CharField(max_length=300)
    template = models.CharField(max_length=160)
    category = models.CharField(max_length=40, default="transactional")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=30, blank=True)
    provider_message_id = models.CharField(max_length=200, blank=True)
    rendered_html = models.TextField(blank=True)
    rendered_text = models.TextField(blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.subject} → {self.recipient_email}"


class JobAlertDelivery(models.Model):
    """Tracks which notices a job alert already sent (prevents duplicate mail)."""

    alert = models.ForeignKey(
        "jobs.JobAlert", on_delete=models.CASCADE, related_name="deliveries"
    )
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alert", "job"], name="unique_alert_delivery")
        ]
