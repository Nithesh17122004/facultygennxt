import logging
import socket
import uuid
from contextlib import closing

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.utils import private_document_upload_to, validate_uploaded_document
from .storage import private_storage

logger = logging.getLogger("facultynxtgen.documents")


class Document(models.Model):
    class Purpose(models.TextChoices):
        CV = "cv", "CV / Resume"
        CERTIFICATE = "certificate", "Certificate"
        NOTIFICATION = "notification", "Recruitment notification"
        INSTITUTION_AUTHORIZATION = "institution_authorization", "Institution authorisation"
        INSTITUTION_REGISTRATION = "institution_registration", "Institution registration"
        APPLICATION_SUPPORT = "application_support", "Application supporting document"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file = models.FileField(
        storage=private_storage,
        upload_to=private_document_upload_to,
        validators=[validate_uploaded_document],
        max_length=255,
    )
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    purpose = models.CharField(max_length=40, choices=Purpose.choices, default=Purpose.OTHER)
    description = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "purpose", "is_deleted"]),
            models.Index(fields=["purpose", "created_at"]),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.get_purpose_display()})"

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if self.file:
            try:
                self.file.delete(save=False)
            except Exception:  # pragma: no cover
                logger.exception("Could not delete private file %s", self.pk)
        self.save(update_fields=["is_deleted", "deleted_at"])


def scan_for_malware(file):
    """Optional ClamAV INSTREAM scan; returns True when clean.

    If ClamAV is not configured, validation still enforces content-type and
    size rules. Production deployments should set CLAMAV_HOST to enable
    malware scanning.
    """
    host = getattr(settings, "CLAMAV_HOST", "")
    if not host:
        return True
    port = getattr(settings, "CLAMAV_PORT", 3310)
    file.seek(0)
    try:
        with closing(socket.create_connection((host, port), timeout=10)) as sock:
            sock.sendall(b"zINSTREAM\x00")
            for chunk in iter(lambda: file.read(8192), b""):
                sock.sendall(len(chunk).to_bytes(4, "big"))
                sock.sendall(chunk)
            sock.sendall(b"\x00\x00\x00\x00")
            response = sock.recv(4096).decode("utf-8", errors="replace")
            return "OK" in response and "FOUND" not in response
    except OSError:
        logger.exception("Malware scanner unavailable; upload rejected for safety.")
        return False
    finally:
        file.seek(0)


def create_document(*, owner, uploaded_file, purpose, description=""):
    from apps.core.utils import file_checksum

    mime_type = validate_uploaded_document(uploaded_file)
    if not scan_for_malware(uploaded_file):
        raise ValueError("This file could not be scanned and was not uploaded.")
    doc = Document(
        owner=owner,
        purpose=purpose,
        description=description,
        original_name=uploaded_file.name[:255],
        mime_type=mime_type,
        size=uploaded_file.size,
        checksum=file_checksum(uploaded_file),
    )
    doc.file.save(uploaded_file.name, uploaded_file, save=False)
    doc.save()
    return doc
