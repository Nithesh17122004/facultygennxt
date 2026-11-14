"""Access control and time-limited signed links for private documents."""
from django.conf import settings
from django.core import signing
from django.urls import reverse

from .models import Document, create_document  # re-exported for service callers

__all__ = [
    "Document",
    "create_document",
    "user_can_access_document",
    "build_download_url",
    "load_download_token",
]

DOWNLOAD_SALT = "facultynxtgen.private-document"


def user_can_access_document(user, document):
    if not user.is_authenticated or document.is_deleted:
        return False
    if user.is_staff:
        return True
    if document.owner_id == user.pk:
        return True

    # Recruiters may access documents attached to applications for their own
    # institution, and recruiter-uploaded institutional evidence.
    if document.application_documents.filter(
        application__job__institution__recruiters__user=user,
        application__job__institution__recruiters__is_active=True,
    ).exists():
        return True
    if document.institution_documents.filter(
        institution__recruiters__user=user,
        institution__recruiters__is_active=True,
    ).exists():
        return True
    if getattr(document, "notification_for_jobs", None) and document.notification_for_jobs.filter(
        institution__recruiters__user=user,
        institution__recruiters__is_active=True,
    ).exists():
        return True
    return False


def build_download_url(document, user):
    token = signing.dumps(
        {"document_id": str(document.pk), "user_id": str(user.pk)},
        salt=DOWNLOAD_SALT,
        compress=True,
    )
    return reverse("documents:download", args=[document.pk]) + f"?token={token}"


def load_download_token(token, max_age_seconds=None):
    if max_age_seconds is None:
        max_age_seconds = getattr(settings, "DOCUMENT_DOWNLOAD_LINK_TTL", 600)
    return signing.loads(token, salt=DOWNLOAD_SALT, max_age=max_age_seconds)
