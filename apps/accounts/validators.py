import re

from django.core.exceptions import ValidationError


def normalize_mobile(value):
    if not value:
        return ""
    digits = re.sub(r"[\s\-()]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValidationError("Enter a valid 10-digit Indian mobile number.")
    return digits


def validate_indian_mobile(value):
    normalize_mobile(value)
