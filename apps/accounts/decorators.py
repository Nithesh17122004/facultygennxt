"""Small decorators for role and account-state checks."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def email_verified_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_email_verified:
            messages.warning(
                request,
                "Verify your email address before using this feature. "
                "We can send you a fresh verification link.",
            )
            return redirect("accounts:verify_email_pending")
        return view_func(request, *args, **kwargs)

    return _wrapped


def candidate_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_candidate:
            raise PermissionDenied("This area is for candidate accounts.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def recruiter_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_recruiter:
            raise PermissionDenied("This area is for institution accounts.")
        if not request.user.is_email_verified:
            messages.warning(
                request,
                "Verify your official email address before accessing the institution dashboard.",
            )
            return redirect("accounts:verify_email_pending")
        return view_func(request, *args, **kwargs)

    return _wrapped


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Administrator access is required.")
        return view_func(request, *args, **kwargs)

    return _wrapped
