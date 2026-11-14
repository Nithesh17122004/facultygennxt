"""Account-related email composition helpers."""
from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.notifications.services import send_email

from .tokens import email_verification_token


def build_verification_url(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return f"{settings.SITE_URL}{reverse('accounts:verify_email', args=[uid, token])}"


def send_verification_email(user):
    return send_email(
        recipient=user.email,
        user=user,
        subject="Verify your email address — FacultyNxtGen",
        template="verify_email",
        category="account",
        context={
            "verification_url": build_verification_url(user),
            "display_name": user.get_short_name(),
        },
    )


def send_welcome_email(user):
    return send_email(
        recipient=user.email,
        user=user,
        subject="Welcome to FacultyNxtGen",
        template="welcome",
        category="account",
        context={
            "display_name": user.get_short_name(),
            "dashboard_url": f"{settings.SITE_URL}{user.get_dashboard_url()}",
        },
    )
