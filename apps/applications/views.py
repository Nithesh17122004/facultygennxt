import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.decorators import candidate_required, email_verified_required, recruiter_required
from apps.audit.services import log_action
from apps.institutions.models import institution_for_user
from apps.jobs.models import Job

from .forms import ApplicationForm, ApplicationNoteForm, ApplicationStatusForm
from .models import Application
from .services import (
    ApplicationError,
    add_internal_note,
    allowed_next_statuses,
    record_external_click,
    submit_application,
    update_application_status,
    withdraw_application,
)

logger = logging.getLogger("facultynxtgen.applications")


def _candidate_profile(user):
    profile = getattr(user, "candidate_profile", None)
    if profile is None:
        from apps.candidates.forms import CandidateProfileForm  # noqa: F401
        from apps.candidates.models import CandidateProfile

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
    return profile


def _institution(request):
    institution = institution_for_user(request.user)
    if institution is None:
        raise PermissionDenied("No active institution is linked to this account.")
    return institution


@candidate_required
@email_verified_required
def apply(request, job_id):
    job = get_object_or_404(
        Job.objects.select_related("institution", "designation", "department", "state", "city"),
        pk=job_id,
    )
    if not job.is_live:
        messages.error(request, "This vacancy is no longer accepting applications.")
        return redirect("jobs:detail", slug=job.slug)
    if job.application_method != Job.ApplicationMethod.INTERNAL:
        messages.info(request, "This institution accepts applications through its official website.")
        return redirect("jobs:detail", slug=job.slug)
    existing = Application.objects.filter(job=job, candidate=request.user).first()
    if existing:
        messages.info(request, "You have already applied to this vacancy.")
        return redirect("applications:candidate_detail", pk=existing.pk)
    profile = _candidate_profile(request.user)
    form = ApplicationForm(
        request.POST or None, request.FILES or None, profile=profile
    )
    if request.method == "POST" and form.is_valid():
        attachment_files = request.FILES.getlist("attachments")[:5]
        try:
            application = submit_application(
                job=job,
                candidate=request.user,
                cover_letter=form.cleaned_data.get("cover_letter", ""),
                resume_file=form.cleaned_data.get("resume"),
                attachment_files=attachment_files,
                request=request,
            )
        except ApplicationError as exc:
            form.add_error(None, str(exc))
        except Exception:
            logger.exception("Unexpected error submitting application")
            form.add_error(None, "We could not submit your application. Please try again.")
        else:
            messages.success(
                request,
                "Application submitted. The institution can now review your profile and documents.",
            )
            return redirect("applications:candidate_detail", pk=application.pk)
    return render(
        request,
        "applications/apply.html",
        {"job": job, "form": form, "profile": profile},
    )


@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def external_click(request, job_id):
    job = get_object_or_404(Job.objects.select_related("institution"), pk=job_id)
    if not job.is_live or job.application_method != Job.ApplicationMethod.EXTERNAL:
        raise Http404("This application link is no longer available.")
    target = job.external_apply_link()
    if not target or not target.startswith(("https://", "http://", "mailto:")):
        messages.error(request, "The official application link is not available. Report this job.")
        return redirect("jobs:detail", slug=job.slug)
    record_external_click(request, job)
    return HttpResponseRedirect(target)


@candidate_required
def candidate_list(request):
    applications = Application.objects.filter(candidate=request.user).select_related(
        "job", "job__institution", "job__designation"
    )
    status = (request.GET.get("status") or "").strip()
    if status in dict(Application.Status.choices):
        applications = applications.filter(status=status)
    counts = {
        row["status"]: row["count"]
        for row in Application.objects.filter(candidate=request.user)
        .values("status")
        .annotate(count=Count("id"))
    }
    paginator = Paginator(applications, 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "applications/candidate_list.html",
        {
            "page_obj": page,
            "status": status,
            "counts": counts,
            "total": paginator.count,
        },
    )


@candidate_required
def candidate_detail(request, pk):
    application = get_object_or_404(
        Application.objects.select_related(
            "job", "job__institution", "job__designation", "job__department", "resume"
        ).prefetch_related("status_events", "documents__document"),
        pk=pk,
        candidate=request.user,
    )
    return render(
        request,
        "applications/candidate_detail.html",
        {"application": application},
    )


@candidate_required
@require_POST
def withdraw(request, pk):
    application = get_object_or_404(Application, pk=pk, candidate=request.user)
    try:
        withdraw_application(application, request.user, request=request)
    except ApplicationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Your application has been withdrawn.")
    return redirect("applications:candidate_detail", pk=application.pk)


@recruiter_required
def recruiter_list(request):
    institution = _institution(request)
    applications = Application.objects.filter(job__institution=institution).select_related(
        "candidate", "job", "job__designation", "job__department"
    )
    status = (request.GET.get("status") or "").strip()
    if status in dict(Application.Status.choices):
        applications = applications.filter(status=status)
    job_id = (request.GET.get("job") or "").strip()
    if job_id:
        applications = applications.filter(job_id=job_id)
    q = (request.GET.get("q") or "").strip()[:120]
    if q:
        applications = applications.filter(
            Q(candidate__full_name__icontains=q)
            | Q(candidate__email__icontains=q)
            | Q(job__title__icontains=q)
        )
    counts = {
        row["status"]: row["count"]
        for row in Application.objects.filter(job__institution=institution)
        .values("status")
        .annotate(count=Count("id"))
    }
    paginator = Paginator(applications, 20)
    page = paginator.get_page(request.GET.get("page"))
    jobs = Job.objects.for_institution(institution).order_by("-created_at")[:100]
    return render(
        request,
        "applications/recruiter_list.html",
        {
            "institution": institution,
            "page_obj": page,
            "status": status,
            "job_id": job_id,
            "q": q,
            "counts": counts,
            "total": paginator.count,
            "jobs": jobs,
        },
    )


@recruiter_required
def recruiter_detail(request, pk):
    institution = _institution(request)
    application = get_object_or_404(
        Application.objects.select_related(
            "candidate",
            "candidate__candidate_profile",
            "job",
            "job__designation",
            "job__department",
            "resume",
            "status_updated_by",
        ).prefetch_related("documents__document", "internal_notes__author", "status_events__actor"),
        pk=pk,
        job__institution=institution,
    )
    allowed = allowed_next_statuses(application)
    status_form = ApplicationStatusForm()
    status_form.fields["status"].choices = [
        (status, dict(Application.Status.choices)[status]) for status in allowed
    ]
    note_form = ApplicationNoteForm()
    if request.method == "POST":
        if "add_note" in request.POST:
            note_form = ApplicationNoteForm(request.POST)
            if note_form.is_valid():
                add_internal_note(application, request.user, note_form.cleaned_data["note"])
                log_action(
                    action="application.note_added",
                    summary=f"Internal note added to application {application.pk}",
                    actor=request.user,
                    entity_type="application",
                    entity_id=application.pk,
                    request=request,
                )
                messages.success(request, "Internal note added.")
                return redirect("applications:recruiter_detail", pk=application.pk)
        elif "update_status" in request.POST:
            status_form = ApplicationStatusForm(request.POST)
            status_form.fields["status"].choices = [
                (status, dict(Application.Status.choices)[status]) for status in allowed
            ]
            if status_form.is_valid():
                try:
                    update_application_status(
                        application,
                        status_form.cleaned_data["status"],
                        request.user,
                        status_form.cleaned_data.get("note", ""),
                        request=request,
                    )
                except ApplicationError as exc:
                    status_form.add_error(None, str(exc))
                else:
                    messages.success(request, "Application status updated and the candidate notified.")
                    return redirect("applications:recruiter_detail", pk=application.pk)
    profile = getattr(application.candidate, "candidate_profile", None)
    snapshot = application.profile_snapshot or {}
    return render(
        request,
        "applications/recruiter_detail.html",
        {
            "institution": institution,
            "application": application,
            "profile": profile,
            "snapshot": snapshot,
            "status_form": status_form,
            "note_form": note_form,
            "allowed_statuses": allowed,
        },
    )
