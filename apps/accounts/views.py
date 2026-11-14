import json
import logging
from datetime import timedelta

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_ratelimit.decorators import ratelimit

from apps.audit.services import log_action
from apps.core.utils import get_client_ip
from apps.notifications.services import notify_user, send_email

from .decorators import email_verified_required
from .forms import (
    AccountDeletionForm,
    AccountIdentityForm,
    CandidateRegistrationForm,
    ChangePasswordForm,
    LoginForm,
    MFADisableForm,
    PasswordResetRequestForm,
    ResendVerificationForm,
    SetNewPasswordForm,
)
from .middleware import safe_next_url
from .models import AccountDeletionRequest, User
from .services import send_verification_email, send_welcome_email
from .tokens import email_verification_token

logger = logging.getLogger("facultynxtgen.security")


@ratelimit(key="ip", rate="6/h", method="POST", block=True)
def register_candidate(request):
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())
    form = CandidateRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            log_action(
                action="account.registered",
                summary="Candidate account registered",
                actor=user,
                entity_type="user",
                entity_id=user.pk,
                request=request,
            )
        send_verification_email(user)
        notify_user(
            user,
            title="Verify your email to get started",
            message="Check your inbox for a verification link. You can browse jobs now; verify before applying or saving jobs.",
            url=reverse("accounts:verify_email_pending"),
            category="account",
        )
        login(
            request,
            user,
            backend="apps.accounts.backends.EmailAuthenticationBackend",
        )
        messages.success(
            request,
            "Your account is ready. We have sent a verification link to your email address.",
        )
        return redirect("candidates:dashboard")
    return render(request, "accounts/register.html", {"form": form})


@never_cache
@ratelimit(key="ip", rate="20/m", method="GET", block=True)
def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    valid = user is not None and email_verification_token.check_token(user, token)
    if valid:
        if not user.email_verified_at:
            user.mark_email_verified()
            log_action(
                action="account.email_verified",
                summary="Email address verified",
                actor=user,
                entity_type="user",
                entity_id=user.pk,
                request=request,
            )
            notify_user(
                user,
                title="Email verified",
                message="Your email address is confirmed. You can now apply for jobs and create alerts.",
                url=user.get_dashboard_url(),
                category="account",
                level="success",
            )
            send_welcome_email(user)
        messages.success(request, "Your email address has been verified.")
        if request.user.is_authenticated and request.user.pk == user.pk:
            return redirect(user.get_dashboard_url())
        return redirect(f"{reverse('accounts:login')}?verified=1")
    return render(
        request,
        "accounts/verify_email_result.html",
        {"valid": False},
        status=400,
    )


@ratelimit(key="ip", rate="6/h", method="POST", block=True)
def resend_verification(request):
    form = ResendVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and not user.email_verified_at:
            send_verification_email(user)
        messages.success(
            request,
            "If that account needs verification, a new link has been sent. Check your inbox and spam folder.",
        )
        return redirect("accounts:verify_email_pending")
    return render(request, "accounts/resend_verification.html", {"form": form})


@login_required
def verify_email_pending(request):
    if request.user.email_verified_at:
        messages.info(request, "Your email address is already verified.")
        return redirect(request.user.get_dashboard_url())
    form = ResendVerificationForm(initial={"email": request.user.email})
    return render(request, "accounts/verify_email_pending.html", {"form": form})


@ratelimit(key="ip", rate="20/m", method="POST", block=True)
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())
    next_url = request.GET.get("next", "")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]
        account = User.objects.filter(email__iexact=email).first()
        if account and account.is_locked:
            form.add_error(
                None,
                "This account is temporarily locked after repeated sign-in attempts. "
                "Try again later or reset your password.",
            )
            log_action(
                action="auth.locked_login_attempt",
                summary="Login attempted on a locked account",
                entity_type="user",
                entity_id=account.pk,
                request=request,
            )
        else:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                with transaction.atomic():
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
                login(request, user)
                request.session.set_expiry(
                    60 * 60 * 24 * 30 if form.cleaned_data.get("remember") else settings.SESSION_COOKIE_AGE
                )
                log_action(
                    action="auth.login",
                    summary="Successful sign-in",
                    actor=user,
                    entity_type="user",
                    entity_id=user.pk,
                    request=request,
                )
                if user.is_staff:
                    messages.info(request, "Signed in. Two-factor verification may be required.")
                else:
                    messages.success(request, f"Welcome back, {user.get_short_name()}.")
                if not user.email_verified_at:
                    messages.warning(
                        request,
                        "Your email is not verified yet. Verify it to apply for jobs and access all features.",
                    )
                return redirect(safe_next_url(request, user.get_dashboard_url()))
            if account is not None:
                with transaction.atomic():
                    account.failed_login_attempts += 1
                    if account.failed_login_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                        account.locked_until = timezone.now() + timedelta(
                            minutes=settings.LOGIN_LOCKOUT_MINUTES
                        )
                        account.failed_login_attempts = 0
                    account.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
                log_action(
                    action="auth.failed_login",
                    summary="Failed sign-in attempt",
                    entity_type="user",
                    entity_id=account.pk,
                    metadata={"ip": get_client_ip(request)},
                    request=request,
                )
            form.add_error(None, "Email or password is incorrect. Please try again.")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_required
def redirect_dashboard(request):
    return redirect(request.user.get_dashboard_url())


@login_required
@require_POST
def logout_view(request):
    log_action(
        action="auth.logout",
        summary="Signed out",
        actor=request.user,
        entity_type="user",
        entity_id=request.user.pk,
        request=request,
    )
    logout(request)
    messages.success(request, "You have been signed out securely.")
    return redirect("core:home")


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def password_reset_request(request):
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            from apps.core.utils import mask_email

            # Tokens are only ever sent to the registered address.
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode
            from django.contrib.auth.tokens import default_token_generator

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.SITE_URL}{reverse('accounts:password_reset_confirm', args=[uid, token])}"
            send_email(
                recipient=user.email,
                user=user,
                subject="Reset your FacultyNxtGen password",
                template="password_reset",
                category="account",
                context={"reset_url": reset_url, "display_name": user.get_short_name()},
            )
            log_action(
                action="auth.password_reset_requested",
                summary="Password reset requested",
                actor=user,
                entity_type="user",
                entity_id=user.pk,
                request=request,
            )
        messages.success(
            request,
            "If an account matches that email, a password reset link is on its way.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/password_reset.html", {"form": form})


@never_cache
def password_reset_confirm(request, uidb64, token):
    from django.contrib.auth.tokens import default_token_generator

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "accounts/password_reset_result.html", {"valid": False}, status=400)
    form = SetNewPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
        if request.user.is_authenticated and request.user.pk == user.pk:
            update_session_auth_hash(request, user)
        log_action(
            action="auth.password_reset_completed",
            summary="Password reset completed",
            actor=user,
            entity_type="user",
            entity_id=user.pk,
            request=request,
        )
        send_email(
            recipient=user.email,
            user=user,
            subject="Your FacultyNxtGen password was changed",
            template="password_changed",
            category="account",
            context={"display_name": user.get_short_name()},
        )
        messages.success(request, "Your password has been updated. You can now sign in.")
        return redirect("accounts:login")
    return render(request, "accounts/password_reset_confirm.html", {"form": form, "valid": True})


class AccountPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("accounts:security")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            action="auth.password_changed",
            summary="Password changed from account settings",
            actor=self.request.user,
            entity_type="user",
            entity_id=self.request.user.pk,
            request=self.request,
        )
        messages.success(self.request, "Your password has been changed.")
        return response


def _qr_data_uri(value):
    import base64
    from io import BytesIO

    image = qrcode.make(value)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


@login_required
@never_cache
def mfa_setup(request):
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if request.method == "POST" and not device:
        pending = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        token = request.POST.get("token", "").strip()
        if pending and pending.verify_token(token):
            pending.confirmed = True
            pending.name = "FacultyNxtGen authenticator"
            pending.save()
            otp_login(request, pending)
            log_action(
                action="security.mfa_enabled",
                summary="TOTP two-factor authentication enabled",
                actor=request.user,
                entity_type="user",
                entity_id=request.user.pk,
                request=request,
            )
            notify_user(
                request.user,
                title="Two-factor authentication enabled",
                message="Your account now requires an authenticator code at sign-in.",
                url=reverse("accounts:security"),
                category="account",
                level="success",
            )
            messages.success(request, "Two-factor authentication is now enabled.")
            return redirect(safe_next_url(request, reverse("accounts:security")))
        messages.error(request, "That code is invalid or has expired. Scan the QR code again and retry.")
    if not device:
        pending = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        if pending is None:
            pending = TOTPDevice.objects.create(
                user=request.user,
                name="FacultyNxtGen authenticator",
                confirmed=False,
            )
        qr = _qr_data_uri(pending.config_url)
        secret = pending.key
    else:
        qr = None
        secret = None
        pending = None
    response = render(
        request,
        "accounts/mfa_setup.html",
        {
            "device": device or pending,
            "qr": qr,
            "secret": secret,
            "enforced": settings.MFA_REQUIRED_FOR_STAFF and request.user.is_staff,
            "next": safe_next_url(request, ""),
        },
    )
    response["Cache-Control"] = "no-store"
    return response


@never_cache
@ratelimit(key="ip", rate="12/m", method="POST", block=True)
@login_required
def mfa_verify(request):
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if device is None:
        return redirect("accounts:mfa_setup")
    if request.user.is_verified():
        return redirect(safe_next_url(request, request.user.get_dashboard_url()))
    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        if device.verify_token(token):
            otp_login(request, device)
            log_action(
                action="security.mfa_verified",
                summary="Two-factor verification completed",
                actor=request.user,
                entity_type="user",
                entity_id=request.user.pk,
                request=request,
            )
            return redirect(safe_next_url(request, request.user.get_dashboard_url()))
        messages.error(request, "That authenticator code is not valid. Check the time on your device and retry.")
    response = render(
        request,
        "accounts/mfa_verify.html",
        {
            "enforced": settings.MFA_REQUIRED_FOR_STAFF and request.user.is_staff,
            "next": safe_next_url(request, ""),
        },
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
def mfa_disable(request):
    if settings.MFA_REQUIRED_FOR_STAFF and request.user.is_staff:
        messages.error(
            request,
            "Two-factor authentication is mandatory for administrator accounts and cannot be disabled here.",
        )
        return redirect("accounts:security")
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if device is None:
        messages.info(request, "Two-factor authentication is not enabled.")
        return redirect("accounts:security")
    form = MFADisableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not device.verify_token(form.cleaned_data["token"]):
            form.add_error("token", "That authenticator code is not valid.")
        else:
            TOTPDevice.objects.filter(user=request.user).delete()
            from django_otp import logout as otp_logout

            otp_logout(request)
            log_action(
                action="security.mfa_disabled",
                summary="Two-factor authentication disabled",
                actor=request.user,
                entity_type="user",
                entity_id=request.user.pk,
                request=request,
            )
            messages.success(request, "Two-factor authentication has been disabled.")
            return redirect("accounts:security")
    return render(request, "accounts/mfa_disable.html", {"form": form})


@login_required
def account_security(request):
    mfa_device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    return render(
        request,
        "accounts/security.html",
        {
            "mfa_device": mfa_device,
            "mfa_required": settings.MFA_REQUIRED_FOR_STAFF and request.user.is_staff,
            "deletion_request": AccountDeletionRequest.objects.filter(
                user=request.user, status=AccountDeletionRequest.Status.PENDING
            ).first(),
        },
    )


@login_required
def account_identity(request):
    form = AccountIdentityForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(
            action="account.identity_updated",
            summary="Account name or mobile updated",
            actor=request.user,
            entity_type="user",
            entity_id=request.user.pk,
            request=request,
        )
        messages.success(request, "Your account details have been updated.")
        return redirect("accounts:identity")
    return render(request, "accounts/identity.html", {"form": form})


@login_required
@ratelimit(key="user", rate="3/h", method="GET", block=True)
def export_data(request):
    user = request.user
    payload = {
        "exported_at": timezone.now().isoformat(),
        "account": {
            "id": str(user.pk),
            "full_name": user.full_name,
            "email": user.email,
            "mobile": user.mobile,
            "role": user.role,
            "email_verified": user.is_email_verified,
            "joined": user.date_joined.isoformat(),
        },
        "candidate_profile": None,
        "applications": [],
        "documents": [],
        "saved_jobs": [],
        "job_alerts": [],
    }
    profile = getattr(user, "candidate_profile", None)
    if profile:
        payload["candidate_profile"] = {
            "headline": profile.headline,
            "highest_qualification": profile.highest_qualification,
            "specialization": profile.specialization,
            "department": profile.department.name if profile.department else "",
            "preferred_designation": profile.preferred_designation.name if profile.preferred_designation else "",
            "preferred_location": profile.preferred_location_display,
            "teaching_experience_years": profile.teaching_experience_years,
            "research_experience_years": profile.research_experience_years,
            "open_to_work": profile.is_open_to_work,
            "share_profile_with_recruiters": profile.share_profile_with_recruiters,
        }
        payload["qualifications"] = [
            {
                "level": item.get_level_display(),
                "degree": item.degree,
                "specialization": item.specialization,
                "institution": item.institution,
                "year": item.year_completed,
            }
            for item in profile.qualifications.all()
        ]
        payload["applications"] = [
            {
                "job_title": app.job.title,
                "institution": app.job.institution.name,
                "status": app.get_status_display(),
                "applied_at": app.applied_at.isoformat(),
            }
            for app in user.applications.select_related("job__institution")
        ]
        payload["saved_jobs"] = [
            {"job": saved.job.title, "saved_at": saved.created_at.isoformat()}
            for saved in user.saved_jobs.select_related("job")
        ]
        payload["job_alerts"] = [
            {"name": alert.name, "keyword": alert.keyword, "active": alert.is_active}
            for alert in user.job_alerts.all()
        ]
    payload["documents"] = [
        {
            "name": doc.original_name,
            "purpose": doc.get_purpose_display(),
            "uploaded_at": doc.created_at.isoformat(),
        }
        for doc in user.documents.filter(is_deleted=False)
    ]
    log_action(
        action="privacy.data_export",
        summary="Account data export downloaded",
        actor=user,
        entity_type="user",
        entity_id=user.pk,
        request=request,
    )
    response = HttpResponse(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    response["Content-Disposition"] = 'attachment; filename="facultynxtgen-account-data.json"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def delete_account(request):
    if not request.user.is_candidate:
        messages.info(
            request,
            "Institution accounts cannot be deleted from this page. Contact support so we can "
            "verify ownership and process your request.",
        )
        return redirect("accounts:security")
    existing = AccountDeletionRequest.objects.filter(
        user=request.user, status=AccountDeletionRequest.Status.PENDING
    ).first()
    form = AccountDeletionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        user = request.user
        with transaction.atomic():
            AccountDeletionRequest.objects.create(
                user=user,
                reason=form.cleaned_data.get("reason", ""),
            )
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            log_action(
                action="privacy.account_deletion_requested",
                summary="Candidate account deactivated and deletion requested",
                actor=user,
                entity_type="user",
                entity_id=user.pk,
                request=request,
            )
        send_email(
            recipient=user.email,
            user=user,
            subject="Your FacultyNxtGen account deletion request",
            template="account_deletion",
            category="account",
            context={
                "display_name": user.get_short_name(),
                "retention_days": settings.CANDIDATE_DATA_RETENTION_DAYS,
            },
        )
        logout(request)
        messages.success(
            request,
            "Your account has been deactivated and a deletion request logged. "
            "You will receive a confirmation email with retention details.",
        )
        return redirect("core:home")
    return render(request, "accounts/delete_account.html", {"form": form, "existing": existing})
