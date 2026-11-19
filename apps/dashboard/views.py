"""Custom staff dashboard: verification, moderation, content and audit."""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.applications.models import Application
from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.core.models import BlogPost, ContactEnquiry, FAQ, NewsletterSubscriber
from apps.institutions.models import Institution, InstitutionDocument
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.jobs.forms import JobRejectForm, JobReviewForm, JobSuspendForm
from apps.jobs.models import Job, JobReport, JobView, JobStatusHistory
from apps.jobs.services import (
    JobWorkflowError,
    approve_job,
    publish_job,
    reject_job,
    suspend_job,
    update_verification_checklist,
)
from apps.notifications.models import EmailLog, Notification
from apps.notifications.services import notify_user, send_email

from .forms import (
    ContentNoteForm,
    InstitutionDecisionForm,
    ReportResolutionForm,
    UserModerationForm,
    AdminJobForm,
)

User = get_user_model()


@staff_required
def home(request):
    today = timezone.localdate()
    last_30 = timezone.now() - timedelta(days=30)
    stats = {
        "candidates": User.objects.filter(role=User.Role.CANDIDATE, is_active=True).count(),
        "institutions": Institution.objects.filter(is_active=True).count(),
        "institutions_pending": Institution.objects.filter(
            verification_status=Institution.VerificationStatus.PENDING
        ).count(),
        "live_jobs": Job.objects.live().count(),
        "jobs_pending": Job.objects.filter(status=Job.Status.PENDING, is_deleted=False).count(),
        "expired_jobs": Job.objects.filter(
            status__in=[Job.Status.PUBLISHED, Job.Status.EXPIRED],
            deadline__lt=today,
            is_deleted=False,
        ).count(),
        "applications": Application.objects.count(),
        "applications_30d": Application.objects.filter(applied_at__gte=last_30).count(),
        "job_views": JobView.objects.count(),
        "open_reports": JobReport.objects.filter(
            status__in=[JobReport.Status.OPEN, JobReport.Status.INVESTIGATING]
        ).count(),
        "enquiries_new": ContactEnquiry.objects.filter(status=ContactEnquiry.Status.NEW).count(),
        "expiring_jobs": Job.objects.live()
        .filter(deadline__lte=today + timedelta(days=3))
        .count(),
    }
    return render(
        request,
        "dashboard/admin/home.html",
        {
            "stats": stats,
            "pending_institutions": Institution.objects.filter(
                verification_status=Institution.VerificationStatus.PENDING
            ).order_by("created_at")[:5],
            "pending_jobs": Job.objects.filter(status=Job.Status.PENDING, is_deleted=False)
            .select_related("institution", "designation", "department")
            .order_by("updated_at")[:6],
            "open_reports": JobReport.objects.filter(
                status__in=[JobReport.Status.OPEN, JobReport.Status.INVESTIGATING]
            ).select_related("job", "job__institution")[:5],
            "recent_audit": AuditLog.objects.select_related("actor")[:8],
        },
    )


# ---------------------------------------------------------------------------
# Institutions
# ---------------------------------------------------------------------------


@staff_required
def institutions(request):
    queryset = Institution.objects.annotate(
        jobs_count=Count("jobs", filter=Q(jobs__is_deleted=False), distinct=True),
        docs_count=Count("verification_documents", distinct=True),
    )
    status = (request.GET.get("status") or "").strip()
    if status in dict(Institution.VerificationStatus.choices):
        queryset = queryset.filter(verification_status=status)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(official_email__icontains=q) | Q(city__name__icontains=q)
        )
    paginator = Paginator(queryset.order_by("verification_status", "-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/admin/institutions.html",
        {
            "page_obj": page,
            "status": status,
            "q": q,
            "status_choices": Institution.VerificationStatus.choices,
            "counts": {
                "pending": Institution.objects.filter(verification_status="pending").count(),
                "verified": Institution.objects.filter(verification_status="verified").count(),
                "suspended": Institution.objects.filter(verification_status="suspended").count(),
                "all": Institution.objects.count(),
            },
        },
    )


@staff_required
def institutions_pending(request):
    return redirect(f"{reverse('dashboard:institutions')}?status=pending")


@staff_required
def institution_detail(request, pk):
    institution = get_object_or_404(
        Institution.objects.select_related("state", "city", "verified_by"), pk=pk
    )
    documents = institution.verification_documents.select_related("document", "uploaded_by")
    recruiters = institution.recruiters.select_related("user").order_by("-is_primary", "created_at")
    jobs = institution.jobs.filter(is_deleted=False).order_by("-created_at")[:10]
    counts = {
        "jobs": institution.jobs.filter(is_deleted=False).count(),
        "live": institution.jobs.live().count(),
        "recruiters": recruiters.filter(is_active=True).count(),
    }
    return render(
        request,
        "dashboard/admin/institution_detail.html",
        {
            "institution": institution,
            "documents": documents,
            "recruiters": recruiters,
            "jobs": jobs,
            "counts": counts,
            "form": InstitutionDecisionForm(
                initial={"decision": institution.verification_status, "notes": institution.verification_notes}
            ),
            "audit_entries": AuditLog.objects.filter(
                entity_type="institution", entity_id=str(institution.pk)
            )[:10],
        },
    )


@staff_required
@require_POST
def institution_decision(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    form = InstitutionDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The verification decision needs a clear reason.")
        return redirect("dashboard:institution_detail", pk=institution.pk)
    decision = form.cleaned_data["decision"]
    notes = form.cleaned_data["notes"]
    previous = institution.verification_status
    institution.verification_status = decision
    institution.verification_notes = notes
    if decision == Institution.VerificationStatus.VERIFIED:
        institution.verified_at = timezone.now()
        institution.verified_by = request.user
        institution.is_active = True
        InstitutionDocument.objects.filter(institution=institution).update(
            status=InstitutionDocument.Status.ACCEPTED
        )
    elif decision == Institution.VerificationStatus.REJECTED:
        institution.verified_at = None
        institution.verified_by = None
        InstitutionDocument.objects.filter(institution=institution).update(
            status=InstitutionDocument.Status.REJECTED
        )
    elif decision == Institution.VerificationStatus.SUSPENDED:
        institution.is_active = True
        institution.jobs.filter(
            status__in=[Job.Status.PENDING, Job.Status.APPROVED]
        ).update(status=Job.Status.SUSPENDED, suspension_reason="Institution suspended by platform review.")
    institution.save()
    log_action(
        action="institution.verification_decision",
        summary=f"Institution {institution.name}: {previous} → {decision}",
        actor=request.user,
        entity_type="institution",
        entity_id=institution.pk,
        metadata={"previous": previous, "decision": decision, "notes": notes[:500]},
        request=request,
    )
    for recruiter in institution.recruiters.filter(is_active=True).select_related("user"):
        notify_user(
            recruiter.user,
            title=f"Institution verification: {institution.get_verification_status_display()}",
            message=notes or f"Your institution verification status is now {institution.get_verification_status_display()}.",
            url=reverse("institutions:profile"),
            category="institution",
            level="success" if decision == Institution.VerificationStatus.VERIFIED else "warning",
        )
    primary = institution.recruiters.filter(is_active=True, is_primary=True).select_related("user").first()
    if primary:
        send_email(
            recipient=primary.user.email,
            user=primary.user,
            subject=f"Institution verification update — {institution.name}",
            template="institution_decision",
            category="institution",
            context={
                "institution": institution,
                "decision": decision,
                "decision_label": institution.get_verification_status_display(),
                "notes": notes,
                "dashboard_url": f"{request.scheme}://{request.get_host()}{reverse('institutions:dashboard')}",
            },
        )
    messages.success(request, f"Verification decision saved for {institution.name}.")
    return redirect("dashboard:institution_detail", pk=institution.pk)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@staff_required
def admin_job_create(request):
    """Publish a vacancy for an employer without requiring an employer login."""
    form = AdminJobForm(request.POST or None, request.FILES or None, action="submit", user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        institution = Institution.objects.filter(name__iexact=data["company_name"].strip()).first()
        if institution and not institution.is_verified:
            form.add_error("company_name", "An institution with this name already exists but is not verified. Review its existing record first.")
        else:
            if institution is None:
                institution = Institution.objects.create(
                    name=data["company_name"].strip(), website=data["company_website"],
                    official_email=data["company_email"], phone=data["company_phone"],
                    contact_person=data["company_contact_person"],
                    contact_designation=data["company_contact_designation"],
                    address=data["company_address"], state=data["state"], city=data["city"],
                    institution_type=data["company_type"],
                    verification_status=Institution.VerificationStatus.VERIFIED,
                    verification_notes="Unclaimed directory profile created by FacultyNxtGen admin for a manually verified vacancy. No institution login was created.",
                    verified_at=timezone.now(), verified_by=request.user, is_active=True,
                )
            job = form.save(commit=False)
            job.institution = institution
            job.posted_by = request.user
            job.status = Job.Status.PUBLISHED
            job.is_platform_posted = True
            job.verified_institution = job.verified_recruiter = True
            job.verified_advertisement = job.verified_application_url = True
            job.verified_deadline = job.verified_eligibility = True
            job.approved_by = request.user
            job.approved_at = job.published_at = timezone.now()
            job.review_notes = "Manually entered and verified by FacultyNxtGen administrator."
            job.save()
            uploaded = data.get("notification_file")
            if uploaded:
                try:
                    doc = create_document(owner=request.user, uploaded_file=uploaded,
                        purpose=Document.Purpose.NOTIFICATION,
                        description=f"Recruitment notification — {job.title}"[:255])
                    job.notification_document = doc
                    job.save(update_fields=["notification_document", "updated_at"])
                except Exception as exc:
                    job.delete()
                    messages.error(request, f"Notification upload failed; vacancy was not retained: {exc}")
                    return redirect("dashboard:admin_job_create")
            JobStatusHistory.objects.create(job=job, from_status="", to_status=Job.Status.PUBLISHED,
                actor=request.user, note="Manually published and verified by FacultyNxtGen admin.")
            log_action(action="job.admin_created",
                summary=f"Admin-created vacancy published: {job.title} — {institution.name}",
                actor=request.user, entity_type="job", entity_id=job.pk,
                metadata={"institution": institution.name, "source": job.source_information}, request=request)
            messages.success(request, "Vacancy published and is now visible in the public job portal.")
            return redirect("dashboard:job_detail", pk=job.pk)
    return render(request, "dashboard/admin/job_create.html", {"form": form})


@staff_required
def jobs(request):
    queryset = Job.objects.filter(is_deleted=False).select_related(
        "institution", "designation", "department", "posted_by"
    )
    status = (request.GET.get("status") or "").strip()
    if status in dict(Job.Status.choices):
        queryset = queryset.filter(status=status)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(institution__name__icontains=q)
            | Q(posted_by__email__icontains=q)
        )
    paginator = Paginator(queryset.order_by("-updated_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    counts = {
        row["status"]: row["count"]
        for row in Job.objects.filter(is_deleted=False).values("status").annotate(count=Count("id"))
    }
    counts["all"] = Job.objects.filter(is_deleted=False).count()
    return render(
        request,
        "dashboard/admin/jobs.html",
        {
            "page_obj": page,
            "status": status,
            "q": q,
            "status_choices": Job.Status.choices,
            "counts": counts,
        },
    )


@staff_required
def jobs_pending(request):
    return redirect(f"{reverse('dashboard:jobs')}?status=pending")


@staff_required
def job_detail(request, pk):
    job = get_object_or_404(
        Job.objects.select_related(
            "institution", "designation", "department", "state", "city", "posted_by", "approved_by"
        ).prefetch_related("status_history", "applications"),
        pk=pk,
        is_deleted=False,
    )
    initial = {
        name: getattr(job, name)
        for name in [
            "verified_institution",
            "verified_recruiter",
            "verified_advertisement",
            "verified_application_url",
            "verified_deadline",
            "verified_eligibility",
        ]
    }
    initial["review_notes"] = job.review_notes
    return render(
        request,
        "dashboard/admin/job_detail.html",
        {
            "job": job,
            "review_form": JobReviewForm(initial=initial, action="publish"),
            "reject_form": JobRejectForm(),
            "suspend_form": JobSuspendForm(),
            "checklist_complete": job.verification_checklist_complete,
            "applications_count": job.applications.count(),
            "audit_entries": AuditLog.objects.filter(
                entity_type="job", entity_id=str(job.pk)
            )[:10],
        },
    )


@staff_required
@require_POST
def job_decision(request, pk):
    job = get_object_or_404(Job.objects.select_related("institution"), pk=pk)
    action = request.POST.get("action", "")
    form_name = request.POST.get("form_name", "review")

    if form_name == "reject":
        form = JobRejectForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Add a clear rejection reason (at least 15 characters).")
            return redirect("dashboard:job_detail", pk=job.pk)
        try:
            reject_job(job, request.user, form.cleaned_data["reason"], request=request)
        except JobWorkflowError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Vacancy rejected. The institution has been notified.")
        return redirect("dashboard:job_detail", pk=job.pk)

    if form_name == "suspend":
        form = JobSuspendForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Add a suspension reason (at least 10 characters).")
            return redirect("dashboard:job_detail", pk=job.pk)
        try:
            suspend_job(job, request.user, form.cleaned_data["reason"], request=request)
        except JobWorkflowError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Vacancy suspended and the institution notified.")
        return redirect("dashboard:job_detail", pk=job.pk)

    review_form = JobReviewForm(request.POST, action="publish")
    if not review_form.is_valid():
        messages.error(request, "Complete every verification checkbox before approval or publishing.")
        return redirect("dashboard:job_detail", pk=job.pk)
    update_verification_checklist(job, review_form.cleaned_data, request.user)
    try:
        if action == "approve":
            approve_job(job, request.user, request=request)
            messages.success(request, "Vacancy approved. Publish it when ready.")
        elif action == "publish":
            publish_job(job, request.user, request=request)
            messages.success(request, "Vacancy published and live on the public site.")
        else:
            messages.success(request, "Verification checklist saved.")
    except JobWorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@staff_required
def reports(request):
    queryset = JobReport.objects.select_related("job", "job__institution", "reported_by", "reviewed_by")
    status = (request.GET.get("status") or "").strip()
    if status in dict(JobReport.Status.choices):
        queryset = queryset.filter(status=status)
    paginator = Paginator(queryset.order_by("status", "-created_at"), 20)
    page = paginator.get_page(request.GET.get("page"))
    counts = {
        row["status"]: row["count"]
        for row in JobReport.objects.values("status").annotate(count=Count("id"))
    }
    return render(
        request,
        "dashboard/admin/reports.html",
        {
            "page_obj": page,
            "status": status,
            "status_choices": JobReport.Status.choices,
            "counts": counts,
        },
    )


@staff_required
def report_detail(request, pk):
    report = get_object_or_404(
        JobReport.objects.select_related("job", "job__institution", "reported_by", "reviewed_by"),
        pk=pk,
    )
    return render(
        request,
        "dashboard/admin/report_detail.html",
        {
            "report": report,
            "form": ReportResolutionForm(
                initial={"status": "resolved", "resolution_notes": report.resolution_notes}
            ),
        },
    )


@staff_required
@require_POST
def resolve_report(request, pk):
    report = get_object_or_404(JobReport.objects.select_related("job"), pk=pk)
    form = ReportResolutionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Add resolution notes before saving the outcome.")
        return redirect("dashboard:report_detail", pk=report.pk)
    report.status = form.cleaned_data["status"]
    report.resolution_notes = form.cleaned_data["resolution_notes"]
    report.reviewed_by = request.user
    report.save(update_fields=["status", "resolution_notes", "reviewed_by", "updated_at"])
    if form.cleaned_data.get("suspend_job") and report.job.status == Job.Status.PUBLISHED:
        try:
            suspend_job(
                report.job,
                request.user,
                "Suspended following a candidate vacancy report.",
                request=request,
            )
        except JobWorkflowError as exc:
            messages.warning(request, str(exc))
    log_action(
        action="job_report.resolved",
        summary=f"Job report {report.pk}: {report.status}",
        actor=request.user,
        entity_type="job_report",
        entity_id=report.pk,
        metadata={"notes": report.resolution_notes[:500]},
        request=request,
    )
    notify_user(
        report.reported_by,
        title="Your vacancy report has been reviewed",
        message="Thank you for helping keep FacultyNxtGen accurate. Our team has completed its review.",
        url=reverse("jobs:detail", args=[report.job.slug]),
        category="job",
        level="info",
    )
    messages.success(request, "Report outcome saved and the reporter notified.")
    return redirect("dashboard:report_detail", pk=report.pk)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@staff_required
def users(request):
    queryset = User.objects.select_related("candidate_profile", "recruiter_profile")
    role = (request.GET.get("role") or "").strip()
    if role in dict(User.Role.choices):
        queryset = queryset.filter(role=role)
    state = (request.GET.get("state") or "").strip()
    if state == "active":
        queryset = queryset.filter(is_active=True)
    elif state == "inactive":
        queryset = queryset.filter(is_active=False)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        queryset = queryset.filter(Q(full_name__icontains=q) | Q(email__icontains=q) | Q(mobile__icontains=q))
    paginator = Paginator(queryset.order_by("-date_joined"), 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/admin/users.html",
        {
            "page_obj": page,
            "role": role,
            "state": state,
            "q": q,
            "role_choices": User.Role.choices,
            "counts": {
                "all": User.objects.count(),
                "candidates": User.objects.filter(role=User.Role.CANDIDATE).count(),
                "recruiters": User.objects.filter(role=User.Role.RECRUITER).count(),
                "staff": User.objects.filter(is_staff=True).count(),
                "inactive": User.objects.filter(is_active=False).count(),
            },
        },
    )


@staff_required
def user_detail(request, pk):
    account = get_object_or_404(User.objects.select_related("candidate_profile"), pk=pk)
    recruiter = getattr(account, "recruiter_profile", None)
    return render(
        request,
        "dashboard/admin/user_detail.html",
        {
            "account": account,
            "recruiter": recruiter,
            "institution": recruiter.institution if recruiter else None,
            "profile": getattr(account, "candidate_profile", None),
            "applications": account.applications.select_related("job", "job__institution")[:10],
            "form": UserModerationForm(),
            "audit_entries": AuditLog.objects.filter(
                Q(entity_type="user", entity_id=str(account.pk)) | Q(actor=account)
            )[:15],
        },
    )


@staff_required
@require_POST
def user_moderate(request, pk):
    account = get_object_or_404(User, pk=pk)
    if account.pk == request.user.pk:
        messages.error(request, "You cannot change your own account status from this screen.")
        return redirect("dashboard:user_detail", pk=account.pk)
    if account.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Only a superuser can moderate a superuser account.")
    form = UserModerationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a valid account action.")
        return redirect("dashboard:user_detail", pk=account.pk)
    activate = form.cleaned_data["action"] == "activate"
    account.is_active = activate
    account.save(update_fields=["is_active", "updated_at"])
    if getattr(account, "recruiter_profile", None):
        recruiter = account.recruiter_profile
        recruiter.is_active = activate
        recruiter.save(update_fields=["is_active", "updated_at"])
    log_action(
        action="user.status_changed",
        summary=f"User {'activated' if activate else 'deactivated'}: {account.email}",
        actor=request.user,
        entity_type="user",
        entity_id=account.pk,
        metadata={"notes": form.cleaned_data.get("notes", "")[:500]},
        request=request,
    )
    messages.success(request, f"Account {'activated' if activate else 'deactivated'}.")
    return redirect("dashboard:user_detail", pk=account.pk)


# ---------------------------------------------------------------------------
# Content and audit
# ---------------------------------------------------------------------------


@staff_required
def content(request):
    enquiries = ContactEnquiry.objects.select_related("handled_by")
    status = (request.GET.get("status") or "").strip()
    if status in dict(ContactEnquiry.Status.choices):
        enquiries = enquiries.filter(status=status)
    return render(
        request,
        "dashboard/admin/content.html",
        {
            "posts": BlogPost.objects.select_related("author")[:20],
            "faqs": FAQ.objects.all()[:30],
            "enquiries": enquiries[:30],
            "newsletter_count": NewsletterSubscriber.objects.filter(is_active=True).count(),
            "email_failures": EmailLog.objects.filter(status=EmailLog.Status.FAILED).count(),
            "status": status,
            "status_choices": ContactEnquiry.Status.choices,
        },
    )


@staff_required
def enquiry_detail(request, pk):
    enquiry = get_object_or_404(ContactEnquiry, pk=pk)
    form = ContentNoteForm(initial={"status": enquiry.status, "admin_notes": enquiry.admin_notes})
    if request.method == "POST":
        form = ContentNoteForm(request.POST)
        if form.is_valid():
            enquiry.status = form.cleaned_data["status"]
            enquiry.admin_notes = form.cleaned_data["admin_notes"]
            enquiry.handled_by = request.user
            enquiry.save(update_fields=["status", "admin_notes", "handled_by", "updated_at"])
            log_action(
                action="contact.enquiry_updated",
                summary=f"Enquiry {enquiry.pk} marked {enquiry.status}",
                actor=request.user,
                entity_type="contact_enquiry",
                entity_id=enquiry.pk,
                request=request,
            )
            messages.success(request, "Enquiry updated.")
            return redirect("dashboard:enquiry_detail", pk=enquiry.pk)
    return render(
        request,
        "dashboard/admin/enquiry_detail.html",
        {"enquiry": enquiry, "form": form},
    )


@staff_required
def audit_log(request):
    queryset = AuditLog.objects.select_related("actor")
    action = (request.GET.get("action") or "").strip()[:80]
    if action:
        queryset = queryset.filter(action__startswith=action)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        queryset = queryset.filter(
            Q(summary__icontains=q) | Q(actor__email__icontains=q) | Q(entity_id__icontains=q)
        )
    paginator = Paginator(queryset, 50)
    page = paginator.get_page(request.GET.get("page"))
    actions = (
        AuditLog.objects.values_list("action", flat=True).distinct().order_by("action")[:100]
    )
    return render(
        request,
        "dashboard/admin/audit.html",
        {"page_obj": page, "action": action, "q": q, "actions": actions},
    )


@staff_required
def team(request):
    members = User.objects.filter(is_staff=True).order_by("-is_superuser", "full_name")
    return render(
        request,
        "dashboard/admin/team.html",
        {
            "members": members,
            "mfa_required": settings.MFA_REQUIRED_FOR_STAFF,
        },
    )
