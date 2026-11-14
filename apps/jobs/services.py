"""Job search, recommendation and verification workflow services."""
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import log_action
from apps.core.constants import INSTITUTION_TYPES
from apps.notifications.models import JobAlertDelivery
from apps.notifications.services import notify_staff, notify_user, send_email

from .models import Department, Designation, Job, JobStatusHistory, JobView

logger = logging.getLogger("facultynxtgen.jobs")

EXPERIENCE_FILTERS = [
    ("0", "Fresher / up to 1 year"),
    ("2", "2+ years"),
    ("5", "5+ years"),
    ("10", "10+ years"),
]
POSTED_FILTERS = [
    ("1", "Last 24 hours"),
    ("7", "Last 7 days"),
    ("30", "Last 30 days"),
]
SORT_OPTIONS = [
    ("latest", "Most recent"),
    ("deadline", "Closing soonest"),
    ("oldest", "Oldest first"),
]


class JobWorkflowError(Exception):
    pass


def absolute(path):
    return f"{settings.SITE_URL}{path}"


def filter_live_jobs(params):
    """Applies validated, composable filters to public vacancies."""
    qs = Job.objects.live().select_related(
        "institution", "designation", "department", "state", "city"
    )
    q = (params.get("q") or "").strip()[:200]
    if q:
        search_filter = (
            Q(title__icontains=q)
            | Q(specialization__icontains=q)
            | Q(description__icontains=q)
            | Q(designation__name__icontains=q)
            | Q(department__name__icontains=q)
            | Q(institution__name__icontains=q)
            | Q(state__name__icontains=q)
            | Q(city__name__icontains=q)
        )
        if connection.vendor == "postgresql":
            try:
                from django.contrib.postgres.search import SearchQuery, SearchVector

                qs = qs.annotate(
                    search_document=SearchVector(
                        "title",
                        "specialization",
                        "description",
                        "institution__name",
                        "designation__name",
                        "department__name",
                        config="english",
                    )
                ).filter(
                    search_filter
                    | Q(search_document=SearchQuery(q, config="english"))
                )
            except Exception:  # pragma: no cover - extension safety
                logger.exception("PostgreSQL full-text search failed; using ORM fallback.")
                qs = qs.filter(search_filter)
        else:
            qs = qs.filter(search_filter)

    state = (params.get("state") or "").strip()
    if state:
        qs = qs.filter(state__slug=state)
    city = (params.get("city") or "").strip()
    if city:
        qs = qs.filter(city__slug=city)
    designation = (params.get("designation") or "").strip()
    if designation:
        qs = qs.filter(designation__slug=designation)
    category = (params.get("category") or "").strip()
    if category in dict(Designation.Category.choices):
        qs = qs.filter(designation__category=category)
    department = (params.get("department") or "").strip()
    if department:
        qs = qs.filter(department__slug=department)
    institution_type = (params.get("institution_type") or "").strip()
    if institution_type in dict(INSTITUTION_TYPES):
        qs = qs.filter(institution__institution_type=institution_type)
    employment_type = (params.get("employment_type") or "").strip()
    if employment_type in dict(Job._meta.get_field("employment_type").choices):
        qs = qs.filter(employment_type=employment_type)
    institution = (params.get("institution") or "").strip()
    if institution:
        qs = qs.filter(institution__slug=institution)

    experience = (params.get("experience") or "").strip()
    if experience.isdigit() and int(experience) <= 40:
        qs = qs.filter(experience_min__lte=int(experience))

    posted = (params.get("posted") or "").strip()
    if posted in {"1", "7", "30"}:
        qs = qs.filter(
            published_at__gte=timezone.now() - timedelta(days=int(posted))
        )

    if params.get("closing") == "soon":
        qs = qs.filter(deadline__lte=timezone.localdate() + timedelta(days=7))

    sort = (params.get("sort") or "latest").strip()
    if sort == "deadline":
        qs = qs.order_by("deadline", "-published_at")
    elif sort == "oldest":
        qs = qs.order_by("published_at", "created_at")
    else:
        qs = qs.order_by("-published_at", "-created_at")
    if connection.vendor == "postgresql" and q:
        qs = qs.distinct()
    return qs


def find_landing_page(slug):
    static_pages = {
        "faculty-jobs-in-india": {
            "title": "Faculty Jobs in India",
            "eyebrow": "Academic careers",
            "intro": "Verified teaching, research and non-teaching vacancies from institutions across India. Review the official notification and eligibility before applying.",
            "filters": {},
            "description": "Explore verified faculty, research and academic job vacancies across India on FacultyNxtGen.",
        },
        "assistant-professor-jobs": {
            "title": "Assistant Professor Jobs",
            "eyebrow": "Teaching roles",
            "intro": "Assistant Professor vacancies for eligible postgraduates, NET/SET-qualified candidates and PhD holders, with the official eligibility and application details for every listing.",
            "filters": {"designation": "assistant-professor"},
            "description": "Find Assistant Professor jobs in colleges and universities across India. Verified vacancies with eligibility and application deadlines.",
        },
        "professor-jobs": {
            "title": "Professor and Associate Professor Jobs",
            "eyebrow": "Senior academia",
            "intro": "Senior faculty positions for experienced academics, including Professor, Associate Professor and leadership roles in higher education.",
            "filters": {"category": "teaching"},
            "description": "Professor and Associate Professor vacancies at Indian universities and colleges, with verified recruitment details.",
        },
        "engineering-college-faculty-jobs": {
            "title": "Engineering College Faculty Jobs",
            "eyebrow": "Technical education",
            "intro": "Faculty opportunities in AICTE-approved engineering colleges and polytechnics, from Computer Science to Civil Engineering.",
            "filters": {"institution_type": "engineering", "category": "teaching"},
            "description": "Engineering college faculty vacancies across India for Assistant Professors, Associates and Professors.",
        },
        "arts-and-science-college-jobs": {
            "title": "Arts and Science College Jobs",
            "eyebrow": "Higher education",
            "intro": "Teaching and research roles in arts, science and commerce colleges, including autonomous institutions and university-affiliated colleges.",
            "filters": {"institution_type": "arts_science"},
            "description": "Arts and Science college faculty jobs across India. Verified teaching opportunities in colleges.",
        },
        "research-fellow-jobs": {
            "title": "Research Fellow Jobs",
            "eyebrow": "Research careers",
            "intro": "JRF, SRF, Research Associate, Postdoctoral and research faculty opportunities funded by universities, CSIR, DST, ICMR and other agencies.",
            "filters": {"category": "research"},
            "description": "Research fellow and postdoctoral vacancies in India, including Junior Research Fellow and Senior Research Fellow roles.",
        },
    }
    if slug in static_pages:
        return static_pages[slug]
    prefix = "faculty-jobs-in-"
    if slug.startswith(prefix):
        state_slug = slug[len(prefix):]
        from apps.core.models import State

        state = State.objects.filter(slug=state_slug, is_active=True).first()
        if state:
            live_count = Job.objects.live().filter(state=state).count()
            if live_count == 0:
                return None
            return {
                "title": f"Faculty Jobs in {state.name}",
                "eyebrow": "State-wise academic careers",
                "intro": f"Verified faculty and research vacancies in {state.name}. Every listing includes the institution's official source, eligibility requirements and application deadline.",
                "filters": {"state": state.slug},
                "description": f"Explore faculty and academic job vacancies in {state.name} on FacultyNxtGen.",
                "state": state,
            }
    return None


def recommend_jobs(profile, limit=6):
    from apps.applications.models import Application

    applied_ids = Application.objects.filter(candidate=profile.user).values_list("job_id", flat=True)
    base = Job.objects.live().select_related(
        "institution", "designation", "department", "state", "city"
    ).exclude(id__in=applied_ids)
    clauses = []
    if profile.preferred_designation_id:
        clauses.append(
            When(designation_id=profile.preferred_designation_id, then=Value(6))
        )
    if profile.department_id:
        clauses.append(When(department_id=profile.department_id, then=Value(4)))
    if profile.preferred_state_id:
        clauses.append(When(state_id=profile.preferred_state_id, then=Value(3)))
    if profile.preferred_city_id:
        clauses.append(When(city_id=profile.preferred_city_id, then=Value(2)))
    keyword = (profile.specialization or "").strip()
    if keyword:
        token = keyword.split(",")[0].strip()[:60]
        if token:
            clauses.append(
                When(
                    Q(title__icontains=token) | Q(specialization__icontains=token),
                    then=Value(2),
                )
            )
    if not clauses:
        return base.order_by("-published_at", "-created_at")[:limit]
    return (
        base.annotate(
            match_score=Case(*clauses, default=Value(0), output_field=IntegerField())
        )
        .filter(match_score__gt=0)
        .order_by("-match_score", "-published_at")[:limit]
    )


def record_job_view(request, job):
    if request.user.is_authenticated and request.user.is_staff:
        return
    if not request.session.session_key:
        request.session.save()
    today = timezone.localdate()
    seed = f"{request.session.session_key}:{job.pk}:{today}"
    session_hash = hashlib.sha256(seed.encode()).hexdigest()
    created = JobView.objects.get_or_create(
        job=job, session_hash=session_hash, viewed_on=today
    )[1]
    if created:
        Job.objects.filter(pk=job.pk).update(views_count=F("views_count") + 1)


def _history(job, actor, note):
    job._status_change_actor = actor
    job._status_change_note = note


def submission_issues(job):
    """Returns human-readable reasons a draft cannot be sent for review."""
    issues = []
    for field, label in [
        ("title", "job title"),
        ("description", "role description"),
        ("required_qualification", "required qualifications"),
        ("eligibility", "eligibility conditions"),
        ("source_information", "official source or reference"),
    ]:
        if not (getattr(job, field, "") or "").strip():
            issues.append(f"Add the {label}.")
    if job.deadline is None:
        issues.append("Add an application deadline.")
    elif job.deadline < timezone.localdate():
        issues.append("The application deadline must be today or later.")
    if not job.notification_document_id and not job.notification_url:
        issues.append("Attach or link the original recruitment notification.")
    if job.application_method == Job.ApplicationMethod.EXTERNAL:
        if not job.external_application_url and not job.external_application_email:
            issues.append("Add the official application URL or recruitment email.")
    if not job.designation_id or not job.department_id or not job.state_id or not job.city_id:
        issues.append("Choose the designation, department, state and city.")
    return issues


def submit_job(job, actor, request=None):
    if job.is_deleted:
        raise JobWorkflowError("This job has been removed.")
    if job.institution.verification_status != "verified":
        raise JobWorkflowError("The institution must be verified before a job can be submitted.")
    if job.deadline is None or job.deadline < timezone.localdate():
        raise JobWorkflowError("Add an application deadline of today or later.")
    if job.status not in {Job.Status.DRAFT, Job.Status.REJECTED}:
        raise JobWorkflowError("Only drafts and rejected jobs can be submitted for review.")
    issues = submission_issues(job)
    if issues:
        raise JobWorkflowError(issues[0])
    job.status = Job.Status.PENDING
    job.rejection_reason = ""
    job.verified_institution = False
    job.verified_recruiter = False
    job.verified_advertisement = False
    job.verified_application_url = False
    job.verified_deadline = False
    job.verified_eligibility = False
    _history(job, actor, "Submitted for verification")
    job.save()
    log_action(
        action="job.submitted",
        summary=f"Job submitted for review: {job.title}",
        actor=actor,
        entity_type="job",
        entity_id=job.pk,
        metadata={"institution": str(job.institution_id)},
        request=request,
    )
    send_email(
        recipient=actor.email,
        user=actor,
        subject="Your vacancy has been submitted for review",
        template="job_submitted",
        category="institution",
        context={"job": job, "job_url": absolute(job.get_absolute_url())},
    )
    notify_staff(
        "New job awaiting verification",
        f"{actor.get_full_name()} submitted “{job.title}” for {job.institution.name}.",
        reverse("dashboard:jobs_pending"),
    )
    return job


def update_verification_checklist(job, cleaned, actor):
    fields = [
        "verified_institution",
        "verified_recruiter",
        "verified_advertisement",
        "verified_application_url",
        "verified_deadline",
        "verified_eligibility",
    ]
    for field in fields:
        setattr(job, field, bool(cleaned.get(field)))
    job.review_notes = cleaned.get("review_notes", "")
    job.save(update_fields=fields + ["review_notes", "updated_at"])


def approve_job(job, actor, request=None):
    if job.status not in {Job.Status.PENDING, Job.Status.REJECTED, Job.Status.APPROVED}:
        raise JobWorkflowError("Only pending jobs can be approved.")
    if not job.verification_checklist_complete:
        raise JobWorkflowError("Complete the verification checklist before approval.")
    if job.institution.verification_status != "verified":
        raise JobWorkflowError("The institution is not verified.")
    job.status = Job.Status.APPROVED
    job.approved_by = actor
    job.approved_at = timezone.now()
    _history(job, actor, "Verification checklist completed; approved")
    job.save()
    log_action(
        action="job.approved",
        summary=f"Job approved: {job.title}",
        actor=actor,
        entity_type="job",
        entity_id=job.pk,
        request=request,
    )
    return job


def publish_job(job, actor, request=None):
    if job.status not in {Job.Status.PENDING, Job.Status.APPROVED, Job.Status.SUSPENDED}:
        raise JobWorkflowError("This job cannot be published from its current status.")
    if not job.verification_checklist_complete:
        raise JobWorkflowError("Complete the verification checklist before publishing.")
    if job.institution.verification_status != "verified":
        raise JobWorkflowError("The institution is not verified.")
    if not job.deadline or job.deadline < timezone.localdate():
        raise JobWorkflowError("The application deadline has passed.")
    first_publication = job.published_at is None
    job.status = Job.Status.PUBLISHED
    job.approved_by = actor
    job.approved_at = timezone.now()
    job.published_at = timezone.now()
    job.suspension_reason = ""
    job._status_change_note = "Approved and published"
    job._status_change_actor = actor
    job.save()
    log_action(
        action="job.published",
        summary=f"Job published: {job.title}",
        actor=actor,
        entity_type="job",
        entity_id=job.pk,
        metadata={"first_publication": first_publication},
        request=request,
    )
    if first_publication:
        send_email(
            recipient=job.posted_by.email,
            user=job.posted_by,
            subject="Your vacancy is now live on FacultyNxtGen",
            template="job_approved",
            category="institution",
            context={"job": job, "job_url": absolute(job.get_absolute_url())},
        )
        notify_user(
            job.posted_by,
            title="Vacancy published",
            message=f"“{job.title}” is now public. Candidates can view and apply according to your selected method.",
            url=reverse("jobs:recruiter_detail", args=[job.pk]),
            category="job",
            level="success",
        )
    return job


def reject_job(job, actor, reason, request=None):
    if not reason.strip():
        raise JobWorkflowError("A rejection reason is required.")
    job.status = Job.Status.REJECTED
    job.rejection_reason = reason.strip()
    _history(job, actor, f"Rejected: {reason[:200]}")
    job.save()
    log_action(
        action="job.rejected",
        summary=f"Job rejected: {job.title}",
        actor=actor,
        entity_type="job",
        entity_id=job.pk,
        metadata={"reason": reason[:500]},
        request=request,
    )
    send_email(
        recipient=job.posted_by.email,
        user=job.posted_by,
        subject="Your FacultyNxtGen vacancy needs changes",
        template="job_rejected",
        category="institution",
        context={
            "job": job,
            "reason": reason,
            "edit_url": absolute(reverse("jobs:recruiter_edit", args=[job.pk])),
        },
    )
    notify_user(
        job.posted_by,
        title="Vacancy needs changes",
        message=f"“{job.title}” was not approved. Review the reason and resubmit.",
        url=reverse("jobs:recruiter_detail", args=[job.pk]),
        category="job",
        level="warning",
    )
    return job


def suspend_job(job, actor, reason, request=None):
    if not reason.strip():
        raise JobWorkflowError("A suspension reason is required.")
    job.status = Job.Status.SUSPENDED
    job.suspension_reason = reason.strip()
    _history(job, actor, f"Suspended: {reason[:200]}")
    job.save()
    log_action(
        action="job.suspended",
        summary=f"Job suspended: {job.title}",
        actor=actor,
        entity_type="job",
        entity_id=job.pk,
        metadata={"reason": reason[:500]},
        request=request,
    )
    notify_user(
        job.posted_by,
        title="Vacancy suspended",
        message=f"“{job.title}” has been suspended. Reason: {reason}",
        url=reverse("jobs:recruiter_detail", args=[job.pk]),
        category="job",
        level="error",
    )
    return job


def expire_job(job, request=None):
    if job.status != Job.Status.PUBLISHED:
        return job
    job.status = Job.Status.EXPIRED
    job._status_change_actor = None
    job._status_change_note = "Application deadline reached"
    job.expiry_notified_at = timezone.now()
    job.save()
    log_action(
        action="job.expired",
        summary=f"Job expired: {job.title}",
        entity_type="job",
        entity_id=job.pk,
        request=request,
    )
    send_email(
        recipient=job.posted_by.email,
        user=job.posted_by,
        subject="Your FacultyNxtGen vacancy has expired",
        template="job_expired",
        category="institution",
        context={
            "job": job,
            "jobs_url": absolute(reverse("jobs:recruiter_list")),
        },
    )
    return job


def expire_due_jobs():
    due = Job.objects.live().filter(deadline__lt=timezone.localdate())
    count = 0
    for job in due:
        expire_job(job)
        count += 1
    return count


def send_due_job_alerts():
    from apps.jobs.models import JobAlert

    sent = 0
    now = timezone.now()
    alerts = JobAlert.objects.filter(is_active=True).select_related(
        "user", "department", "designation", "state", "city"
    )
    for alert in alerts:
        threshold = now - timedelta(days=1 if alert.frequency == "daily" else 7)
        if alert.last_sent_at and alert.last_sent_at > threshold:
            continue
        since = alert.last_sent_at or (now - timedelta(days=7))
        candidates = (
            Job.objects.live()
            .filter(published_at__gte=since)
            .exclude(jobalertdelivery__alert=alert)
            .select_related("institution", "designation", "department", "state", "city")[:50]
        )
        matches = [job for job in candidates if alert.matches(job)][:8]
        if not matches:
            alert.last_sent_at = now
            alert.save(update_fields=["last_sent_at", "updated_at"])
            continue
        send_email(
            recipient=alert.user.email,
            user=alert.user,
            subject=f"{len(matches)} new academic vacancy{'ies' if len(matches) != 1 else ''} matching your alert",
            template="job_alert",
            category="job_alert",
            context={
                "alert": alert,
                "jobs": matches,
                "manage_url": absolute(reverse("candidates:job_alerts")),
            },
        )
        with transaction.atomic():
            for job in matches:
                JobAlertDelivery.objects.get_or_create(alert=alert, job=job)
            alert.last_sent_at = now
            alert.save(update_fields=["last_sent_at", "updated_at"])
        sent += 1
    return sent


def homepage_data():
    from apps.institutions.models import Institution

    live = Job.objects.live()
    latest = live.select_related(
        "institution", "designation", "department", "state", "city"
    ).order_by("-published_at", "-created_at")[:6]
    by_category = {
        "teaching": live.filter(designation__category="teaching").count(),
        "research": live.filter(designation__category="research").count(),
        "non_teaching": live.filter(designation__category="non_teaching").count(),
    }
    departments = (
        Department.objects.filter(is_active=True)
        .annotate(live_count=Count("jobs", filter=Q(jobs__status="published", jobs__is_deleted=False)))
        .filter(live_count__gt=0)
        .order_by("-live_count", "name")[:8]
    )
    states = (
        live.values("state__name", "state__slug")
        .annotate(live_count=Count("id"))
        .order_by("-live_count")[:10]
    )
    hiring_institutions = (
        Institution.objects.filter(verification_status="verified", is_active=True)
        .annotate(live_jobs_count=Count("jobs", filter=Q(jobs__status="published", jobs__is_deleted=False)))
        .filter(live_jobs_count__gt=0)
        .order_by("-live_jobs_count", "name")[:6]
    )
    stats = {
        "live_jobs": live.count(),
        "institutions": Institution.objects.filter(
            verification_status="verified", is_active=True
        ).count(),
        "departments": Department.objects.filter(is_active=True).count(),
        "candidates": 0,
    }
    from django.contrib.auth import get_user_model

    stats["candidates"] = get_user_model().objects.filter(
        role="candidate", is_active=True
    ).count()
    return {
        "latest_jobs": latest,
        "category_counts": by_category,
        "departments": departments,
        "states": states,
        "hiring_institutions": hiring_institutions,
        "home_stats": stats,
    }
