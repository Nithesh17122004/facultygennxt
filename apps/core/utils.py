"""Shared validation and utility helpers."""
import hashlib
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

PDF_MAGIC = b"%PDF-"
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_MAGIC = b"RIFF"


def _random_upload_path(prefix, filename):
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_DOCUMENT_EXTENSIONS | settings.ALLOWED_IMAGE_EXTENSIONS:
        ext = ""
    return f"{prefix}/{secrets.token_hex(20)}{ext}"


def private_document_upload_to(instance, filename):
    """Upload path for private candidate/application documents."""
    return _random_upload_path("private", filename)


def institution_logo_upload_to(instance, filename):
    """Upload path for institution logos served as public brand assets."""
    return _random_upload_path("institutions/logos", filename)


def random_upload_to(prefix):
    """Returns an upload_to callable using random keys and a safe extension.

    Prefer the named upload helpers above for model fields: migration files can
    serialize top-level functions, not closures.
    """

    def _upload_to(instance, filename):
        return _random_upload_path(prefix, filename)

    return _upload_to


def validate_uploaded_document(file):
    """Validates a PDF/JPG/PNG by size, extension and real file signature.

    Returns the detected MIME type so callers can store an accurate value.
    """
    if file.size > settings.MAX_DOCUMENT_SIZE:
        raise ValidationError(
            f"File is too large. Maximum size is {settings.MAX_DOCUMENT_SIZE // (1024 * 1024)} MB."
        )
    ext = Path(file.name).suffix.lower()
    if ext not in settings.ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError("Upload a PDF, JPG or PNG file.")

    file.seek(0)
    header = file.read(16)
    file.seek(0)
    if header.startswith(PDF_MAGIC):
        try:
            file.seek(0)
            content = file.read()
            if b"%%EOF" not in content[-2048:]:
                raise ValidationError("This PDF appears to be incomplete or corrupted.")
        finally:
            file.seek(0)
        return "application/pdf"
    if header.startswith(JPEG_MAGIC):
        try:
            image = Image.open(file)
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError("This image appears to be corrupted.") from exc
        finally:
            file.seek(0)
        return "image/jpeg"
    if header.startswith(PNG_MAGIC):
        try:
            image = Image.open(file)
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError("This image appears to be corrupted.") from exc
        finally:
            file.seek(0)
        return "image/png"
    raise ValidationError("The file content does not match an allowed PDF, JPG or PNG format.")


def validate_uploaded_image(file):
    if file.size > settings.MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Image is too large. Maximum size is {settings.MAX_IMAGE_SIZE // (1024 * 1024)} MB."
        )
    ext = Path(file.name).suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Upload a JPG, PNG or WEBP image.")
    file.seek(0)
    header = file.read(16)
    file.seek(0)
    if not (
        header.startswith(JPEG_MAGIC)
        or header.startswith(PNG_MAGIC)
        or (header.startswith(WEBP_MAGIC) and header[8:12] == b"WEBP")
    ):
        raise ValidationError("The file content is not a valid JPG, PNG or WEBP image.")
    try:
        image = Image.open(file)
        image.verify()
        if image.width < 32 or image.height < 32:
            raise ValidationError("Image dimensions are too small.")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("This image is invalid or corrupted.") from exc
    finally:
        file.seek(0)
    return file


def file_checksum(file):
    digest = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b""):
        digest.update(chunk)
    file.seek(0)
    return digest.hexdigest()


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def mask_email(email):
    try:
        local, domain = email.split("@", 1)
    except (ValueError, AttributeError):
        return "hidden"
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def initials(name):
    parts = [part for part in (name or "").strip().split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "FN"


def indian_rupees(amount):
    """Formats an amount with Indian digit grouping, without the currency sign."""
    try:
        value = int(round(float(amount)))
    except (TypeError, ValueError):
        return "0"
    negative = value < 0
    digits = str(abs(value))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"-{digits}" if negative else digits


def salary_display(minimum, maximum, period):
    from django.utils.safestring import mark_safe

    labels = {"month": "month", "year": "year", "consolidated": "consolidated"}
    suffix = labels.get(period, "")
    if minimum and maximum and minimum != maximum:
        value = f"₹{indian_rupees(minimum)} – ₹{indian_rupees(maximum)}"
    elif minimum:
        value = f"₹{indian_rupees(minimum)}"
    elif maximum:
        value = f"₹{indian_rupees(maximum)}"
    else:
        return "Not disclosed"
    return mark_safe(f"{value} <span class='text-muted fw-normal'>/ {suffix}</span>")


def truncate(text, length=160):
    text = " ".join((text or "").split())
    if len(text) <= length:
        return text
    return text[: length - 1].rsplit(" ", 1)[0] + "…"
