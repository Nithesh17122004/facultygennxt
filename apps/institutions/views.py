import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.decorators import recruiter_required
from apps.accounts.forms import AccountIdentityForm, SetNewPasswordForm
from apps.accounts.services import send_verification_email
from apps.audit.services import log_action
from apps.core.constants import INSTITUTION_TYPES
from apps.core.models import City, State
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.jobs.models import Job, JobView
from apps.notifications.models import EmailPreference
from apps.notifications.services import notify_staff, send_email

from .forms import (
    InstitutionDocumentUploadForm,
    InstitutionProfileForm,
    InstitutionRegistrationForm,
    RecruiterInviteForm,
    RecruiterProfileForm,
)
from .models import Institution, InstitutionDocument, Recruiter, institution_for_user

logger = logging.getLogger("facultynxtgen.institutions")
User = get_user_model()


def _require_institution(request):
    institution = institution_for_user(request.user)
    if institution is None:
        raise PermissionDenied("No active institution is linked to this account.")
    return institution


@ratelimit(key="ip", rate="700/h", method="POST", block=True)
def register(request):
    if request.user.is_authenticated:
        return redirect(request.user.get_dashboard_url())
    form = InstitutionRegistrationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=form.cleaned_data["official_email"],
                    password=form.cleaned_data["password1"],
                    full_name=form.cleaned_data["contact_person"],
                    mobile=form.cleaned_data["phone"],
                    role=User.Role.RECRUITER,
                    terms_accepted_at=timezone.now(),
                )
                institution = Institution.objects.create(
                    name=form.cleaned_data["institution_name"],
                    website=form.cleaned_data["website"],
                    official_email=form.cleaned_data["official_email"],
                    phone=form.cleaned_data["phone"],
                    contact_person=form.cleaned_data["contact_person"],
                    contact_designation=form.cleaned_data["contact_designation"],
                    contact_phone=form.cleaned_data["phone"],
                    contact_email=form.cleaned_data["official_email"],
                    address=form.cleaned_data["address"],
                    state=form.cleaned_data["state"],
                    city=form.cleaned_data["city"],
                    pincode=form.cleaned_data["pincode"],
                    institution_type=form.cleaned_data["institution_type"],
                    established_year=form.cleaned_data.get("established_year"),
                )
                Recruiter.objects.create(
                    user=user,
                    institution=institution,
                    designation=form.cleaned_data["contact_designation"],
                    phone=form.cleaned_data["phone"],
                    is_primary=True,
                )
                authorization = create_document(
                    owner=user,
                    uploaded_file=form.cleaned_data["authorization_document"],
                    purpose=Document.Purpose.INSTITUTION_AUTHORIZATION,
                    description="Institution authorisation letter",
                )
                InstitutionDocument.objects.create(
                    institution=institution,
                    document=authorization,
                    doc_type=InstitutionDocument.DocType.AUTHORIZATION,
                    uploaded_by=user,
                )
                if form.cleaned_data.get("registration_document"):
                    registration_doc = create_document(
                        owner=user,
                        uploaded_file=form.cleaned_data["registration_document"],
                        purpose=Document.Purpose.INSTITUTION_REGISTRATION,
                        description="Institution registration certificate",
                    )
                    InstitutionDocument.objects.create(
                        institution=institution,
                        document=registration_doc,
                        doc_type=InstitutionDocument.DocType.REGISTRATION,
                        uploaded_by=user,
                    )
        except IntegrityError:
            logger.exception("Institution registration race condition")
            form.add_error(None, "An account or institution with these details already exists.")
        else:
            send_verification_email(user)
            send_email(
                recipient=user.email,
                user=user,
                subject="Institution registration received — FacultyNxtGen",
                template="institution_received",
                category="institution",
                context={
                    "institution": institution,
                    "display_name": user.get_short_name(),
                    "verification_window": settings.INSTITUTION_VERIFICATION_WINDOW_DAYS,
                },
            )
            notify_staff(
                "New institution needs verification",
                f"{institution.name} registered and submitted verification documents.",
                reverse("dashboard:institutions_pending"),
            )
            log_action(
                action="institution.registered",
                summary=f"Institution registered: {institution.name}",
                actor=user,
                entity_type="institution",
                entity_id=institution.pk,
                request=request,
            )
            login(
                request,
                user,
                backend="apps.accounts.backends.EmailAuthenticationBackend",
            )
            messages.success(
                request,
                "Your institution account is ready. Verify your email and await document review "
                "before publishing vacancies.",
            )
            return redirect("institutions:dashboard")
    return render(
        request,
        "institutions/register.html",
        {
            "form": form,
            "institution_types": INSTITUTION_TYPES,
            "states": State.objects.all().order_by("name"),
            "cities": City.objects.all().select_related("state").order_by("name"),
        },
    )


def directory(request):
    institutions = Institution.objects.filter(
        verification_status=Institution.VerificationStatus.VERIFIED,
        is_active=True,
    ).annotate(
        live_jobs_count=Count(
            "jobs",
            filter=Q(
                jobs__status=Job.Status.PUBLISHED,
                jobs__is_deleted=False,
                jobs__deadline__gte=timezone.localdate(),
            ),
        )
    )
    q = (request.GET.get("q") or "").strip()[:150]
    if q:
        institutions = institutions.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        )
    state = (request.GET.get("state") or "").strip()
    if state:
        institutions = institutions.filter(state__slug=state)
    city = (request.GET.get("city") or "").strip()
    if city:
        institutions = institutions.filter(city__slug=city)
    institution_type = (request.GET.get("type") or "").strip()
    if institution_type in dict(INSTITUTION_TYPES):
        institutions = institutions.filter(institution_type=institution_type)
    institutions = institutions.order_by("-live_jobs_count", "name")
    paginator = Paginator(institutions, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "institutions/directory.html",
        {
            "page_obj": page,
            "states": State.objects.filter(is_active=True),
            "cities": City.objects.filter(is_active=True).select_related("state"),
            "institution_types": INSTITUTION_TYPES,
            "total_count": paginator.count,
        },
    )


def detail(request, slug):
    institution = get_object_or_404(
        Institution.objects.prefetch_related("jobs__designation", "jobs__department"),
        slug=slug,
        is_active=True,
    )
    is_staff_preview = request.user.is_authenticated and request.user.is_staff
    if institution.verification_status != Institution.VerificationStatus.VERIFIED and not is_staff_preview:
        raise Http404("Institution not found.")
    jobs = (
        institution.jobs.live()
        .select_related("designation", "department", "state", "city", "institution")
        .order_by("-published_at")[:20]
    )
    total_live = institution.jobs.live().count()
    return render(
        request,
        "institutions/detail.html",
        {
            "institution": institution,
            "jobs": jobs,
            "total_live": total_live,
            "is_staff_preview": is_staff_preview,
        },
    )


@recruiter_required
def dashboard(request):
    institution = _require_institution(request)
    jobs = Job.objects.for_institution(institution)
    status_counts = {
        "published": jobs.filter(status=Job.Status.PUBLISHED, deadline__gte=timezone.localdate()).count(),
        "pending": jobs.filter(status=Job.Status.PENDING).count(),
        "draft": jobs.filter(status=Job.Status.DRAFT).count(),
        "rejected": jobs.filter(status=Job.Status.REJECTED).count(),
        "expired": jobs.filter(status=Job.Status.EXPIRED).count(),
    }
    from apps.applications.models import Application

    applications = Application.objects.filter(job__institution=institution).select_related(
        "candidate", "job", "job__designation"
    )
    recent_applications = applications.order_by("-applied_at")[:6]
    views = JobView.objects.filter(job__institution=institution).count()
    documents = institution.verification_documents.select_related("document")
    profile_fields = [
        institution.logo,
        institution.description,
        institution.website,
        institution.contact_person,
        institution.contact_designation,
        institution.address,
    ]
    profile_completion = int(round(sum(bool(value) for value in profile_fields) / len(profile_fields) * 100))
    return render(
        request,
        "institutions/dashboard.html",
        {
            "institution": institution,
            "status_counts": status_counts,
            "applications_count": applications.count(),
            "new_applications": applications.filter(status="submitted").count(),
            "shortlisted_count": applications.filter(status="shortlisted").count(),
            "recent_applications": recent_applications,
            "views": views,
            "documents": documents,
            "profile_completion": profile_completion,
            "recent_jobs": jobs.select_related("designation", "department")[:5],
        },
    )


@recruiter_required
def profile(request):
    institution = _require_institution(request)
    form = InstitutionProfileForm(
        request.POST or None, request.FILES or None, instance=institution
    )
    documents = institution.verification_documents.select_related("document", "uploaded_by")
    upload_form = InstitutionDocumentUploadForm()
    if request.method == "POST" and form.is_valid():
        old_logo = institution.logo.name if institution.logo else ""
        institution = form.save()
        if old_logo and institution.logo and old_logo != institution.logo.name:
            institution.logo.storage.delete(old_logo)
        log_action(
            action="institution.profile_updated",
            summary=f"Institution profile updated: {institution.name}",
            actor=request.user,
            entity_type="institution",
            entity_id=institution.pk,
            request=request,
        )
        messages.success(request, "Institution profile updated.")
        return redirect("institutions:profile")
    return render(
        request,
        "institutions/profile.html",
        {
            "institution": institution,
            "form": form,
            "documents": documents,
            "upload_form": upload_form,
            "verification_window_days": settings.INSTITUTION_VERIFICATION_WINDOW_DAYS,
        },
    )


@recruiter_required
@require_POST
def upload_document(request):
    institution = _require_institution(request)
    form = InstitutionDocumentUploadForm(request.POST, request.FILES)
    if form.is_valid():
        document = create_document(
            owner=request.user,
            uploaded_file=form.cleaned_data["file"],
            purpose=Document.Purpose.INSTITUTION_AUTHORIZATION
            if form.cleaned_data["doc_type"] == InstitutionDocument.DocType.AUTHORIZATION
            else Document.Purpose.INSTITUTION_REGISTRATION,
            description=f"Institution document — {institution.name}",
        )
        InstitutionDocument.objects.create(
            institution=institution,
            document=document,
            doc_type=form.cleaned_data["doc_type"],
            uploaded_by=request.user,
        )
        log_action(
            action="institution.document_uploaded",
            summary=f"Verification document uploaded for {institution.name}",
            actor=request.user,
            entity_type="institution",
            entity_id=institution.pk,
            request=request,
        )
        notify_staff(
            "Institution uploaded a document",
            f"{institution.name} added verification evidence. Review the institution file.",
            reverse("dashboard:institution_detail", args=[institution.pk]),
        )
        messages.success(request, "Document uploaded securely. Our verification team can review it.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    return redirect("institutions:profile")


@recruiter_required
@require_POST
def request_verification(request):
    institution = _require_institution(request)
    if institution.verification_status == Institution.VerificationStatus.VERIFIED:
        messages.info(request, "Your institution is already verified.")
        return redirect("institutions:profile")
    if institution.verification_status == Institution.VerificationStatus.SUSPENDED:
        messages.error(request, "A suspended institution cannot request verification. Contact support.")
        return redirect("institutions:profile")
    cache_key = f"institution-verification-request:{institution.pk}"
    if cache.get(cache_key):
        messages.info(request, "Your verification request is already in the review queue.")
        return redirect("institutions:profile")
    institution.verification_status = Institution.VerificationStatus.PENDING
    institution.save(update_fields=["verification_status", "updated_at"])
    if institution.verification_documents.exists():
        InstitutionDocument.objects.filter(institution=institution).update(
            status=InstitutionDocument.Status.PENDING
        )
    cache.set(cache_key, True, 60 * 60 * 12)
    notify_staff(
        "Institution requested verification",
        f"{institution.name} requested review of its verification documents.",
        reverse("dashboard:institution_detail", args=[institution.pk]),
    )
    log_action(
        action="institution.verification_requested",
        summary=f"Verification requested: {institution.name}",
        actor=request.user,
        entity_type="institution",
        entity_id=institution.pk,
        request=request,
    )
    messages.success(
        request,
        "Verification review requested. Our team typically responds within "
        f"{settings.INSTITUTION_VERIFICATION_WINDOW_DAYS} working days.",
    )
    return redirect("institutions:profile")


@recruiter_required
def recruiters(request):
    institution = _require_institution(request)
    team = institution.recruiters.select_related("user").order_by("-is_primary", "created_at")
    return render(
        request,
        "institutions/recruiters.html",
        {
            "institution": institution,
            "team": team,
            "active_count": team.filter(is_active=True).count(),
        },
    )


@recruiter_required
def recruiter_invite(request):
    institution = _require_institution(request)
    form = RecruiterInviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=form.cleaned_data["email"],
                    password=None,
                    full_name=form.cleaned_data["full_name"],
                    mobile=form.cleaned_data["phone"] or None,
                    role=User.Role.RECRUITER,
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])
                recruiter = Recruiter.objects.create(
                    user=user,
                    institution=institution,
                    designation=form.cleaned_data.get("designation", ""),
                    phone=form.cleaned_data.get("phone", ""),
                    is_active=True,
                    invited_by=request.user,
                )
        except IntegrityError:
            form.add_error("email", "An account with this email already exists.")
        else:
            invite_url = _recruiter_invite_url(user)
            send_email(
                recipient=user.email,
                user=user,
                subject=f"{institution.name} invited you to FacultyNxtGen",
                template="recruiter_invite",
                category="institution",
                context={
                    "institution": institution,
                    "inviter": request.user,
                    "invite_url": invite_url,
                    "designation": recruiter.designation,
                },
            )
            log_action(
                action="institution.recruiter_invited",
                summary=f"Recruiter invited: {user.email}",
                actor=request.user,
                entity_type="recruiter",
                entity_id=recruiter.pk,
                request=request,
            )
            messages.success(request, f"Invitation sent to {user.email}.")
            return redirect("institutions:recruiters")
    return render(
        request,
        "institutions/recruiter_invite.html",
        {"form": form, "institution": institution},
    )


def _recruiter_invite_url(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.SITE_URL}{reverse('institutions:accept_invite', args=[uid, token])}"


@ratelimit(key="ip", rate="20/m", method="GET", block=True)
def accept_invite(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, role=User.Role.RECRUITER)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, token) or not user.is_active:
        return render(request, "accounts/password_reset_result.html", {"valid": False}, status=400)
    form = SetNewPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        if not user.email_verified_at:
            user.mark_email_verified()
        login(request, user, backend="apps.accounts.backends.EmailAuthenticationBackend")
        log_action(
            action="institution.recruiter_invite_accepted",
            summary="Recruiter invitation accepted",
            actor=user,
            entity_type="recruiter",
            entity_id=user.pk,
            request=request,
        )
        messages.success(request, "Your recruiter account is ready.")
        return redirect("institutions:dashboard")
    return render(
        request,
        "accounts/accept_invite.html",
        {"form": form, "invited_user": user, "institution": user.recruiter_profile.institution},
    )


@recruiter_required
@require_POST
def recruiter_toggle(request, pk):
    institution = _require_institution(request)
    recruiter = get_object_or_404(Recruiter, pk=pk, institution=institution)
    if recruiter.user_id == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("institutions:recruiters")
    if recruiter.is_primary:
        messages.error(request, "The primary recruiter cannot be deactivated. Transfer ownership by contacting support.")
        return redirect("institutions:recruiters")
    recruiter.is_active = not recruiter.is_active
    recruiter.save(update_fields=["is_active", "updated_at"])
    recruiter.user.is_active = recruiter.is_active
    recruiter.user.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="institution.recruiter_status_changed",
        summary=f"Recruiter {'activated' if recruiter.is_active else 'deactivated'}: {recruiter.user.email}",
        actor=request.user,
        entity_type="recruiter",
        entity_id=recruiter.pk,
        request=request,
    )
    messages.success(request, "Recruiter access updated.")
    return redirect("institutions:recruiters")


@recruiter_required
@require_POST
def recruiter_resend_invite(request, pk):
    institution = _require_institution(request)
    recruiter = get_object_or_404(Recruiter, pk=pk, institution=institution, is_active=True)
    if not recruiter.user.has_usable_password():
        send_email(
            recipient=recruiter.user.email,
            user=recruiter.user,
            subject=f"Your {institution.name} recruiter invitation",
            template="recruiter_invite",
            category="institution",
            context={
                "institution": institution,
                "inviter": request.user,
                "invite_url": _recruiter_invite_url(recruiter.user),
                "designation": recruiter.designation,
            },
        )
        messages.success(request, "A fresh invitation link has been sent.")
    else:
        messages.info(request, "This recruiter has already activated their account.")
    return redirect("institutions:recruiters")


@recruiter_required
def settings_view(request):
    institution = _require_institution(request)
    identity_form = AccountIdentityForm(request.POST or None, instance=request.user)
    recruiter_form = RecruiterProfileForm(
        request.POST or None, instance=request.user.recruiter_profile
    )
    if request.method == "POST":
        if identity_form.is_valid() and recruiter_form.is_valid():
            identity_form.save()
            recruiter_form.save()
            messages.success(request, "Account settings updated.")
            return redirect("institutions:settings")
    preference, _ = EmailPreference.objects.get_or_create(user=request.user)
    return render(
        request,
        "institutions/settings.html",
        {
            "institution": institution,
            "identity_form": identity_form,
            "recruiter_form": recruiter_form,
            "preference": preference,
        },
    )
