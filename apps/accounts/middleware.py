"""Authentication hardening middleware."""
import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

logger = logging.getLogger("facultynxtgen.security")

MFA_ALLOWED_PREFIXES = (
    "/accounts/mfa/",
    "/accounts/logout/",
    "/accounts/password-reset/",
    "/static/",
    "/media/",
    "/admin/logout/",
)


class StaffMFAEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not request.path.startswith(MFA_ALLOWED_PREFIXES):
            from django_otp.plugins.otp_totp.models import TOTPDevice

            has_confirmed = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
            next_url = request.get_full_path()
            if has_confirmed and not user.is_verified():
                messages.info(request, "Enter your authenticator code to continue.")
                return redirect(
                    f"{reverse('accounts:mfa_verify')}?{urlencode({'next': next_url})}"
                )
            if (
                settings.MFA_REQUIRED_FOR_STAFF
                and user.is_staff
                and not has_confirmed
            ):
                messages.warning(
                    request,
                    "Two-factor authentication is required for administrator accounts.",
                )
                return redirect(
                    f"{reverse('accounts:mfa_setup')}?{urlencode({'next': next_url})}"
                )
        return self.get_response(request)


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = request.user
        if user.is_authenticated:
            now = timezone.now()
            if not user.last_seen_at or (now - user.last_seen_at).total_seconds() > 300:
                try:
                    from django.contrib.auth import get_user_model

                    get_user_model().objects.filter(pk=user.pk).update(last_seen_at=now)
                except Exception:  # pragma: no cover
                    logger.exception("Could not update last_seen_at")
        return response


def safe_next_url(request, fallback):
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback
