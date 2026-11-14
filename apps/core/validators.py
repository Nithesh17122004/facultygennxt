"""Backwards-compatible validator entry points used by model definitions."""
from .utils import validate_uploaded_document, validate_uploaded_image


def validate_image_file(file):
    return validate_uploaded_image(file)


def validate_document_file(file):
    return validate_uploaded_document(file)
