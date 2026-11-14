"""Institution-side job management."""
import logging
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import email_verified_required, recruiter_required
from apps.audit.services import log_action
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.institutions.models import institution_for_user
from apps.notifications.services import notify_staff

from .forms import JobForm
from .models import Job, JobView
from .services import JobWorkflowError, submit_job

logger = logging.getLogger("facultynxtgen.jobs")

STATUS_FILTERS = [
    ("", "All vacancies"),
    (Job.Status.DRAFT, "Drafts"),
    (Job.Status.PENDING, "In review"),
    (Job.Status.PUBLISHED, "Live"),
    (Job.Status.REJECTED, "Needs changes"),
    (Job.Status.EXPIRED, "Expired"),
    (Job.Status.SUSPENDED, "Suspended"),
]


def _institution(request):
    institution = institution_for_user(request.user)
    if institution is None:
        raise PermissionDenied("No active institution is linked to this account.")
    return institution


def _job_for(request, pk):
    institution = _institution(request)
    job = get_object_or_404(
        Job.objects.select_related("designation", "department", "state", "city", "institution"),
        pk=pk,
        institution=institution,
        is_deleted=False,
    )
    return institution, job


def _form_context(institution, form, action, job=None):
    return {
        "institution": institution,
        "form": form,
        "action": action,
        "job": job,
        "is_edit": job is not None,
    }


def _save_notification_document(request, form, job):
    uploaded = form.cleaned_data.get("notification_file")
    if not uploaded:
        return
    try:
        document = create_document(
            owner=request.user,
            uploaded_file=uploaded,
            purpose=Document.Purpose.NOTIFICATION,
            description=f"Recruitment notification — {job.title}"[:255],
        )
    except Exception as exc:  # validation errors are user-facing
        form.add_error("notification_file", str(exc))
        return
    job.notification_document = document
    job.save(update_fields=["notification_document", "updated_at"])


@recruiter_required
@email_verified_required
def recruiter_list(request):
    institution = _institution(request)
    jobs = Job.objects.for_institution(institution).select_related(
        "designation", "department", "state", "city"
    )
    status = (request.GET.get("status") or "").strip()
    if status in dict(Job.Status.choices):
        jobs = jobs.filter(status=status)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        jobs = jobs.filter(Q(title__icontains=q) | Q(department__name__icontains=q))
    counts = {
        row["status"]: row["count"]
        for row in Job.objects.for_institution(institution)
        .values("status")
        .annotate(count=Count("id"))
    }
    counts["all"] = sum(counts.values())
    paginator = Paginator(jobs.order_by("-created_at"), 15)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/recruiter_list.html",
        {
            "institution": institution,
            "page_obj": page,
            "status": status,
            "q": q,
            "counts": counts,
            "status_filters": STATUS_FILTERS,
        },
    )


@recruiter_required
@email_verified_required
def recruiter_create(request):
    institution = _institution(request)
    if not institution.is_verified:
        messages.warning(
            request,
            "Your institution must be verified before you can create a vacancy. "
            "Complete your profile and verification documents first.",
        )
        return redirect("institutions:profile")

    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    form = JobForm(
        request.POST or None,
        request.FILES or None,
        action=action,
        institution=institution,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.institution = institution
        job.posted_by = request.user
        job.status = Job.Status.DRAFT
        job.save()
        _save_notification_document(request, form, job)
        if form.errors:
            return render(
                request,
                "jobs/recruiter_form.html",
                _form_context(institution, form, action, job),
            )
        log_action(
            action="job.created",
            summary=f"Job created: {job.title}",
            actor=request.user,
            entity_type="job",
            entity_id=job.pk,
            request=request,
        )
        if action == "submit":
            try:
                submit_job(job, request.user, request=request)
            except JobWorkflowError as exc:
                messages.warning(request, f"Draft saved, but it cannot be submitted yet: {exc}")
            else:
                messages.success(request, "Your vacancy has been submitted for verification.")
        else:
            messages.success(request, "Draft saved. Complete the remaining details and submit for review.")
        return redirect("jobs:recruiter_detail", pk=job.pk)
    return render(
        request,
        "jobs/recruiter_form.html",
        _form_context(institution, form, action),
    )


@recruiter_required
@email_verified_required
def recruiter_edit(request, pk):
    institution, job = _job_for(request, pk)
    if not job.can_edit():
        messages.info(request, "This vacancy can no longer be edited. View it for its current status.")
        return redirect("jobs:recruiter_detail", pk=job.pk)
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"
    form = JobForm(
        request.POST or None,
        request.FILES or None,
        instance=job,
        action=action,
        institution=institution,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.institution = institution
        job.save()
        _save_notification_document(request, form, job)
        if form.errors:
            return render(
                request,
                "jobs/recruiter_form.html",
                _form_context(institution, form, action, job),
            )
        log_action(
            action="job.updated",
            summary=f"Job updated: {job.title}",
            actor=request.user,
            entity_type="job",
            entity_id=job.pk,
            request=request,
        )
        if action == "submit":
            try:
                submit_job(job, request.user, request=request)
            except JobWorkflowError as exc:
                messages.warning(request, f"Changes saved, but the vacancy cannot be submitted yet: {exc}")
            else:
                messages.success(request, "Your updated vacancy has been submitted for verification.")
        else:
            messages.success(request, "Draft updated.")
        return redirect("jobs:recruiter_detail", pk=job.pk)
    return render(
        request,
        "jobs/recruiter_form.html",
        _form_context(institution, form, action, job),
    )


@recruiter_required
@email_verified_required
def recruiter_detail(request, pk):
    institution, job = _job_for(request, pk)
    applications = job.applications.select_related(
        "candidate", "candidate__candidate_profile"
    ).order_by("-applied_at")
    counts = {
        row["status"]: row["count"]
        for row in applications.values("status").annotate(count=Count("id"))
    }
    checklist = [
        ("Institution verified", job.verified_institution),
        ("Recruiter authorised", job.verified_recruiter),
        ("Vacancy matches notification", job.verified_advertisement),
        ("Application URL verified", job.verified_application_url),
        ("Deadline verified", job.verified_deadline),
        ("Eligibility verified", job.verified_eligibility),
    ]
    return render(
        request,
        "jobs/recruiter_detail.html",
        {
            "institution": institution,
            "job": job,
            "applications": applications[:8],
            "application_count": applications.count(),
            "new_applications": counts.get("submitted", 0),
            "shortlisted": counts.get("shortlisted", 0),
            "status_history": job.status_history.select_related("actor")[:10],
            "checklist": checklist,
            "checklist_complete": job.verification_checklist_complete,
            "view_count": JobView.objects.filter(job=job).count(),
            "can_edit": job.can_edit(),
            "can_delete": job.can_delete(),
        },
    )


@recruiter_required
@require_POST
def recruiter_submit(request, pk):
    institution, job = _job_for(request, pk)
    try:
        submit_job(job, request.user, request=request)
    except JobWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        notify_staff(
            "Vacancy submitted for verification",
            f"{institution.name} submitted “{job.title}”.",
            reverse("dashboard:jobs_pending"),
        )
        messages.success(request, "Vacancy submitted for verification.")
    return redirect("jobs:recruiter_detail", pk=job.pk)


@recruiter_required
@require_POST
def recruiter_delete(request, pk):
    _, job = _job_for(request, pk)
    if not job.can_delete():
        messages.error(request, "Only drafts or vacancies needing changes can be deleted.")
        return redirect("jobs:recruiter_detail", pk=job.pk)
    title = job.title
    job.is_deleted = True
    job.deleted_at = timezone.now()
    job.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
    log_action(
        action="job.deleted",
        summary=f"Job deleted: {title}",
        actor=request.user,
        entity_type="job",
        entity_id=job.pk,
        request=request,
    )
    messages.success(request, "The vacancy has been removed from your dashboard.")
    return redirect("jobs:recruiter_list")


@recruiter_required
@email_verified_required
def recruiter_analytics(request, pk):
    institution, job = _job_for(request, pk)
    today = timezone.localdate()
    start = today - timedelta(days=29)
    raw = {
        row["viewed_on"]: row["count"]
        for row in JobView.objects.filter(job=job, viewed_on__gte=start)
        .values("viewed_on")
        .annotate(count=Count("id"))
    }
    series = []
    for offset in range(30):
        day = start + timedelta(days=offset)
        series.append({"date": day, "views": raw.get(day, 0)})
    max_views = max([point["views"] for point in series] or [1]) or 1
    for point in series:
        point["height"] = max(4, int(point["views"] / max_views * 100))
    applications = job.applications.values("status").annotate(count=Count("id"))
    applications_by_status = [
        {
            "status": row["status"],
            "label": dict(job.applications.model.Status.choices).get(row["status"], row["status"]),
            "count": row["count"],
            "percentage": round(row["count"] * 100 / max(1, job.applications.count())),
        }
        for row in applications
    ]
    return render(
        request,
        "jobs/recruiter_analytics.html",
        {
            "institution": institution,
            "job": job,
            "series": series,
            "total_views": sum(point["views"] for point in series),
            "applications_by_status": applications_by_status,
            "application_count": job.applications.count(),
            "external_clicks": job.external_clicks.count(),
        },
    )
