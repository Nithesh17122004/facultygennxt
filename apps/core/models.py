import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import INDIAN_STATES


def validate_image_file(file):
    """Validate an uploaded image by size, extension and real image content."""
    from apps.core.utils import validate_uploaded_image

    validate_uploaded_image(file)


def state_default():
    return INDIAN_STATES[0][0]


class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    code = models.CharField(max_length=3, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "state / UT"

    def __str__(self):
        return self.name


class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["state", "slug"], name="unique_city_slug_per_state"
            )
        ]
        indexes = [models.Index(fields=["state", "is_active"])]
        verbose_name_plural = "cities"

    def __str__(self):
        return f"{self.name}, {self.state.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=60, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    consent_text = models.CharField(max_length=300, blank=True)
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def confirm(self):
        self.is_active = True
        self.confirmed_at = timezone.now()
        self.unsubscribed_at = None
        self.save(update_fields=["is_active", "confirmed_at", "unsubscribed_at", "updated_at"])

    def unsubscribe(self):
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["is_active", "unsubscribed_at", "updated_at"])

    def get_unsubscribe_url(self):
        return f"{settings.SITE_URL}{reverse('core:newsletter_unsubscribe', args=[self.unsubscribe_token])}"


class ContactEnquiry(models.Model):
    class Purpose(models.TextChoices):
        GENERAL = "general", "General enquiry"
        ADVERTISE = "advertise", "Advertise with us"
        INSTITUTION = "institution", "Institutional support"
        CANDIDATE = "candidate", "Candidate support"
        PRIVACY = "privacy", "Privacy or data request"
        REPORT = "report", "Report a concern"
        PARTNERSHIP = "partnership", "Partnerships"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        SPAM = "spam", "Spam"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    purpose = models.CharField(max_length=30, choices=Purpose.choices, default=Purpose.GENERAL)
    subject = models.CharField(max_length=200)
    message = models.TextField(max_length=5000)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    admin_notes = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handled_enquiries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "contact enquiries"
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.subject} — {self.name}"


class FAQ(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField(max_length=4000)
    category = models.CharField(max_length=80, default="General")
    sort_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    excerpt = models.TextField(max_length=500)
    content = models.TextField(help_text="Plain text with blank lines between paragraphs.")
    cover_image = models.ImageField(
        upload_to="blog/",
        blank=True,
        null=True,
        validators=[validate_image_file, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="blog_posts"
    )
    category = models.CharField(max_length=80, default="Career guidance")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("core:blog_detail", args=[self.slug])

    @property
    def is_public(self):
        return self.status == self.Status.PUBLISHED and self.published_at and self.published_at <= timezone.now()
