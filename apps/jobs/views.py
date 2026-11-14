import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.decorators import candidate_required, email_verified_required
from apps.applications.models import Application
from apps.audit.services import log_action
from apps.core.constants import EMPLOYMENT_TYPES, INSTITUTION_TYPES
from apps.core.models import City, State
from apps.core.utils import truncate
from apps.notifications.services import notify_staff

from .forms import JobReportForm
from .models import Department, Designation, Job, JobReport, SavedJob
from .services import filter_live_jobs, find_landing_page, record_job_view

logger = logging.getLogger("facultynxtgen.jobs")


def _filter_options():
    return {
        "states": State.objects.filter(is_active=True),
        "cities": City.objects.filter(is_active=True).select_related("state"),
        "designations": Designation.objects.filter(is_active=True),
        "departments": Department.objects.filter(is_active=True),
        "institution_types": INSTITUTION_TYPES,
        "employment_types": EMPLOYMENT_TYPES,
        "teaching_designations": Designation.objects.filter(is_active=True, category="teaching"),
        "research_designations": Designation.objects.filter(is_active=True, category="research"),
        "non_teaching_designations": Designation.objects.filter(is_active=True, category="non_teaching"),
    }


def find_jobs(request):
    jobs = filter_live_jobs(request.GET)
    paginator = Paginator(jobs, 10)
    page = paginator.get_page(request.GET.get("page"))
    search_terms = {
        key: request.GET.get(key, "")
        for key in [
            "q",
            "state",
            "city",
            "designation",
            "department",
            "institution_type",
            "employment_type",
            "experience",
            "posted",
            "closing",
            "sort",
        ]
    }
    return render(
        request,
        "jobs/find.html",
        {
            "page_obj": page,
            "total": paginator.count,
            "search_terms": search_terms,
            "active_filter_count": sum(
                1
                for key, value in search_terms.items()
                if value and key not in {"sort"}
            ),
            **_filter_options(),
        },
    )


CATEGORY_META = {
    "teaching": {
        "title": "Teaching Jobs",
        "eyebrow": "Faculty opportunities",
        "intro": "Verified teaching roles — from Assistant Professor to Principal — in universities, autonomous colleges and professional institutions across India.",
        "description": "Explore verified teaching vacancies for faculty and academic leaders across India.",
    },
    "research": {
        "title": "Research Jobs",
        "eyebrow": "Research careers",
        "intro": "JRF, SRF, Research Associate, Postdoctoral and research faculty opportunities in funded projects and university research centres.",
        "description": "Find research fellow, postdoctoral and research faculty vacancies across India.",
    },
    "non_teaching": {
        "title": "Non-Teaching Jobs",
        "eyebrow": "Institutional roles",
        "intro": "Librarian, laboratory, technical, administrative and finance roles that keep academic institutions running.",
        "description": "Non-teaching academic institution jobs including librarian, lab and administrative roles.",
    },
}


def category_jobs(request, category):
    if category not in CATEGORY_META:
        raise Http404
    params = request.GET.copy()
    params["category"] = category
    jobs = filter_live_jobs(params)
    paginator = Paginator(jobs, 10)
    page = paginator.get_page(request.GET.get("page"))
    meta = CATEGORY_META[category]
    designations = Designation.objects.filter(is_active=True, category=category)
    return render(
        request,
        "jobs/category.html",
        {
            "page_obj": page,
            "total": paginator.count,
            "category": category,
            "meta": meta,
            "designations": designations,
            "search_terms": {
                key: request.GET.get(key, "")
                for key in ["q", "state", "city", "designation", "employment_type", "experience", "sort"]
            },
            **_filter_options(),
        },
    )


def landing_page(request, slug):
    page = find_landing_page(slug)
    if page is None:
        raise Http404("This job collection does not exist.")
    params = request.GET.copy()
    for key, value in page.get("filters", {}).items():
        params[key] = value
    jobs = filter_live_jobs(params)
    paginator = Paginator(jobs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/landing.html",
        {
            "page_obj": page_obj,
            "total": paginator.count,
            "landing": page,
            "page_title": f"{page['title']} — FacultyNxtGen",
            "meta_description": page["description"],
            "canonical_url": f"{settings.SITE_URL}{request.path}",
            "search_terms": {
                key: request.GET.get(key, "")
                for key in ["q", "state", "city", "designation", "department", "employment_type", "sort"]
            },
            **_filter_options(),
        },
    )


def state_landing_page(request, state_slug):
    page = find_landing_page(f"faculty-jobs-in-{state_slug}")
    if page is None:
        raise Http404("No live vacancies are available in this state yet.")
    return landing_page(request, f"faculty-jobs-in-{state_slug}")


def job_detail(request, slug):
    job = get_object_or_404(
        Job.objects.select_related(
            "institution", "designation", "department", "state", "city", "posted_by"
        ).prefetch_related("applications"),
        slug=slug,
    )
    is_staff = request.user.is_authenticated and request.user.is_staff
    if job.is_deleted:
        raise Http404
    closed = job.deadline is not None and job.deadline < timezone.localdate()
    if not is_staff:
        if job.status != Job.Status.PUBLISHED:
            raise Http404
        if job.institution.verification_status != "verified" or not job.institution.is_active:
            raise Http404
        if closed:
            return render(
                request,
                "jobs/expired.html",
                {
                    "job": job,
                    "similar_jobs": Job.objects.live()
                    .filter(department=job.department)
                    .exclude(pk=job.pk)
                    .select_related("institution", "designation", "department", "state", "city")
                    .order_by("-published_at", "-created_at")[:3],
                },
                status=410,
            )
        record_job_view(request, job)
    is_preview = job.status != Job.Status.PUBLISHED
    saved = False
    existing_application = None
    if request.user.is_authenticated:
        if request.user.is_candidate:
            saved = SavedJob.objects.filter(user=request.user, job=job).exists()
            existing_application = Application.objects.filter(
                job=job, candidate=request.user
            ).first()
    apply_target = ""
    if job.application_method == Job.ApplicationMethod.INTERNAL:
        apply_target = reverse("applications:apply", args=[job.pk])
        if not request.user.is_authenticated:
            apply_target = f"{reverse('accounts:login')}?next={apply_target}"
    else:
        apply_target = reverse("applications:external_click", args=[job.pk])

    schema = _job_schema(request, job)
    return render(
        request,
        "jobs/detail.html",
        {
            "job": job,
            "saved": saved,
            "existing_application": existing_application,
            "apply_target": apply_target,
            "is_preview": is_preview,
            "is_closed": closed,
            "job_schema_json": json.dumps(schema).replace("<", "\\u003c"),
            "shared_url": request.build_absolute_uri(job.get_absolute_url()),
            "report_url": reverse("jobs:report", args=[job.slug]),
            "similar_jobs": Job.objects.live()
            .filter(department=job.department)
            .exclude(pk=job.pk)
            .select_related("institution", "designation", "department", "state", "city")
            .order_by("-published_at", "-created_at")[:3],
        },
    )


def _job_schema(request, job):
    employment_map = {
        "full_time": "FULL_TIME",
        "part_time": "PART_TIME",
        "contract": "CONTRACTOR",
        "temporary": "TEMPORARY",
        "visiting": "PART_TIME",
    }
    schema = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": truncate(job.description, 4000),
        "identifier": {
            "@type": "PropertyValue",
            "name": job.institution.name,
            "value": str(job.id),
        },
        "datePosted": (job.published_at or job.created_at).date().isoformat(),
        "validThrough": f"{job.deadline.isoformat()}T23:59:59+05:30" if job.deadline else None,
        "employmentType": employment_map.get(job.employment_type, "FULL_TIME"),
        "hiringOrganization": {
            "@type": "Organization",
            "name": job.institution.name,
            "sameAs": job.institution.website,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.city.name,
                "addressRegion": job.state.name,
                "addressCountry": "IN",
            },
        },
        "url": f"{settings.SITE_URL}{job.get_absolute_url()}",
        "directApply": job.application_method == Job.ApplicationMethod.INTERNAL,
        "educationRequirements": truncate(job.required_qualification, 500),
        "experienceRequirements": {
            "@type": "OccupationalExperienceRequirements",
            "monthsOfExperience": int(job.experience_min) * 12,
        },
    }
    if job.salary_is_disclosed:
        schema["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": "INR",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": float(job.salary_min or job.salary_max),
                "maxValue": float(job.salary_max or job.salary_min),
                "unitText": "MONTH" if job.salary_period == "month" else "YEAR",
            },
        }
    return {key: value for key, value in schema.items() if value not in (None, "")}


@candidate_required
@email_verified_required
@require_POST
def toggle_save(request, slug):
    job = get_object_or_404(Job.objects.filter(is_deleted=False), slug=slug)
    saved = SavedJob.objects.filter(user=request.user, job=job).first()
    if saved:
        saved.delete()
        messages.success(request, "Job removed from your saved list.")
    else:
        SavedJob.objects.get_or_create(user=request.user, job=job)
        messages.success(request, "Job saved. You can review it from your dashboard.")
    next_url = request.POST.get("next") or job.get_absolute_url()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("jobs:detail", slug=job.slug)


@login_required
def report(request, slug):
    job = get_object_or_404(Job, slug=slug, is_deleted=False)
    if not request.user.is_email_verified:
        messages.warning(request, "Verify your email address before reporting a vacancy.")
        return redirect("accounts:verify_email_pending")
    existing = JobReport.objects.filter(job=job, reported_by=request.user).first()
    form = JobReportForm(request.POST or None)
    if existing:
        messages.info(request, "You have already reported this vacancy. Our team is reviewing it.")
        return redirect("jobs:detail", slug=job.slug)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.job = job
        report.reported_by = request.user
        try:
            report.save()
        except IntegrityError:
            messages.info(request, "You have already reported this vacancy.")
            return redirect("jobs:detail", slug=job.slug)
        log_action(
            action="job.reported",
            summary=f"Job reported: {job.title}",
            actor=request.user,
            entity_type="job_report",
            entity_id=report.pk,
            metadata={"reason": report.reason},
            request=request,
        )
        notify_staff(
            "Job reported by candidate",
            f"{request.user.get_full_name()} reported “{job.title}” for {report.get_reason_display()}.",
            reverse("dashboard:reports"),
        )
        messages.success(
            request,
            "Thank you. Our verification team will review the vacancy and take appropriate action.",
        )
        return redirect("jobs:detail", slug=job.slug)
    return render(
        request,
        "jobs/report.html",
        {"job": job, "form": form},
    )
