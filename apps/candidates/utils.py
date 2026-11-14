"""Candidate model helpers and validation."""
from django.core.exceptions import ValidationError

from apps.core.utils import validate_uploaded_image


def validate_image(file):
    validate_uploaded_image(file)


def validate_document_owner(document, user, allowed_purposes):
    if document is None:
        return
    if document.owner_id != user.pk or document.is_deleted:
        raise ValidationError("The selected document is not available.")
    if document.purpose not in allowed_purposes:
        raise ValidationError("The selected document type is not valid here.")
