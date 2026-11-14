"""Application submission, access control and status workflow."""
import hashlib
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import log_action
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.institutions.models import institution_for_user
from apps.notifications.services import notify_user, send_email

from .models import (
    Application,
    ApplicationDocument,
    ApplicationNote,
    ApplicationStatusEvent,
)

logger = logging.getLogger("facultynxtgen.applications")


class ApplicationError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    Application.Status.SUBMITTED: {
        Application.Status.UNDER_REVIEW,
        Application.Status.SHORTLISTED,
        Application.Status.REJECTED,
    },
    Application.Status.UNDER_REVIEW: {
        Application.Status.SHORTLISTED,
        Application.Status.REJECTED,
    },
    Application.Status.SHORTLISTED: {
        Application.Status.SELECTED,
        Application.Status.REJECTED,
    },
    Application.Status.SELECTED: set(),
    Application.Status.REJECTED: set(),
    Application.Status.WITHDRAWN: set(),
}


def allowed_next_statuses(application):
    return sorted(ALLOWED_TRANSITIONS.get(application.status, set()))


def _snapshot(profile):
    qualifications = [
        {
            "degree": q.degree,
            "level": q.get_level_display(),
            "specialization": q.specialization,
            "institution": q.institution,
            "year": q.year_completed,
            "grade": q.percentage_or_grade,
        }
        for q in profile.qualifications.all()
    ]
    return {
        "full_name": profile.user.get_full_name(),
        "email": profile.user.email,
        "mobile": profile.user.mobile or "",
        "headline": profile.headline,
        "highest_qualification": profile.highest_qualification,
        "ug_degree": profile.ug_degree,
        "pg_degree": profile.pg_degree,
        "phd_status": profile.get_phd_status_display(),
        "specialization": profile.specialization,
        "department": profile.department.name if profile.department else "",
        "teaching_experience_years": profile.teaching_experience_years,
        "research_experience_years": profile.research_experience_years,
        "current_designation": profile.current_designation,
        "current_institution": profile.current_institution,
        "preferred_location": profile.preferred_location_display,
        "publications_count": profile.publications.count(),
        "qualifications": qualifications,
        "teaching_history": [
            {
                "designation": item.designation,
                "institution": item.institution,
                "period": item.duration_label,
            }
            for item in profile.teaching_experiences.all()[:8]
        ],
        "research_history": [
            {
                "role": item.role,
                "institution": item.institution,
                "period": item.duration_label,
            }
            for item in profile.research_experiences.all()[:8]
        ],
        "snapshot_at": timezone.now().isoformat(),
    }


def _copy_document(source, user, label):
    try:
        with source.file.open("rb") as handle:
            django_file = File(handle, name=source.original_name or "document.pdf")
            copy = create_document(
                owner=user,
                uploaded_file=django_file,
                purpose=Document.Purpose.APPLICATION_SUPPORT,
                description=label,
            )
        return copy
    except Exception as exc:
        logger.exception("Could not copy document %s for application", source.pk)
        raise ApplicationError("One of your documents could not be attached. Re-upload it and try again.") from exc


def submit_application(*, job, candidate, cover_letter, resume_file, attachment_files, request=None):
    if not candidate.is_email_verified:
        raise ApplicationError("Verify your email address before applying.")
    if job.application_method != job.ApplicationMethod.INTERNAL:
        raise ApplicationError("This vacancy uses the institution's external application process.")
    if not job.is_live:
        raise ApplicationError("This vacancy is no longer accepting applications.")
    if Application.objects.filter(job=job, candidate=candidate).exists():
        raise ApplicationError("You have already applied to this vacancy.")
    profile = getattr(candidate, "candidate_profile", None)
    if profile is None:
        raise ApplicationError("Complete your candidate profile before applying.")
    if not resume_file and not (profile.cv_id and not profile.cv.is_deleted):
        raise ApplicationError("Upload a CV before applying.")

    snapshot = _snapshot(profile)
    try:
        with transaction.atomic():
            application = Application.objects.create(
                job=job,
                candidate=candidate,
                cover_letter=cover_letter.strip(),
                profile_snapshot=snapshot,
                status=Application.Status.SUBMITTED,
            )
            if resume_file:
                resume_document = create_document(
                    owner=candidate,
                    uploaded_file=resume_file,
                    purpose=Document.Purpose.APPLICATION_SUPPORT,
                    description=f"Application CV — {job.title}",
                )
            else:
                resume_document = _copy_document(profile.cv, candidate, f"Application CV — {job.title}")
            application.resume = resume_document
            application.save(update_fields=["resume", "updated_at"])
            ApplicationDocument.objects.create(
                application=application,
                document=resume_document,
                label="CV / Resume",
            )
            for index, uploaded in enumerate(attachment_files[:5], start=1):
                copied = create_document(
                    owner=candidate,
                    uploaded_file=uploaded,
                    purpose=Document.Purpose.APPLICATION_SUPPORT,
                    description=f"Supporting document {index} — {job.title}",
                )
                ApplicationDocument.objects.create(
                    application=application,
                    document=copied,
                    label=uploaded.name[:160],
                )
            ApplicationStatusEvent.objects.create(
                application=application,
                from_status="",
                to_status=Application.Status.SUBMITTED,
                actor=candidate,
                note="Application submitted through FacultyNxtGen",
            )
    except IntegrityError as exc:
        raise ApplicationError("You have already applied to this vacancy.") from exc

    log_action(
        action="application.submitted",
        summary=f"Application submitted: {job.title}",
        actor=candidate,
        entity_type="application",
        entity_id=application.pk,
        metadata={"job": str(job.pk), "institution": str(job.institution_id)},
        request=request,
    )
    _notify_recruiters(application)
    notify_user(
        candidate,
        title="Application submitted",
        message=f"Your application for “{job.title}” at {job.institution.name} has been received.",
        url=reverse("applications:candidate_detail", args=[application.pk]),
        category="application",
        level="success",
    )
    send_email(
        recipient=candidate.email,
        user=candidate,
        subject=f"Application received — {job.title}",
        template="application_received",
        category="application",
        context={
            "application": application,
            "job": job,
            "institution": job.institution,
            "application_url": f"{settings.SITE_URL}{reverse('applications:candidate_detail', args=[application.pk])}",
            "official_url": job.external_apply_link(),
        },
    )
    return application


def _notify_recruiters(application):
    recruiters = application.job.institution.recruiters.filter(
        is_active=True, user__is_active=True
    ).select_related("user")
    seen = set()
    for recruiter in recruiters:
        if recruiter.user_id in seen:
            continue
        seen.add(recruiter.user_id)
        notify_user(
            recruiter.user,
            title="New application received",
            message=f"{application.candidate.get_full_name()} applied for “{application.job.title}”.",
            url=reverse("applications:recruiter_detail", args=[application.pk]),
            category="application",
        )
    recipients = []
    primary = recruiters.filter(is_primary=True).first()
    if primary:
        recipients.append(primary.user)
    poster = application.job.posted_by
    if poster.is_active and poster.pk not in seen:
        recipients.append(poster)
    email_seen = set()
    for recipient in recipients:
        if recipient.pk in email_seen:
            continue
        email_seen.add(recipient.pk)
        send_email(
            recipient=recipient.email,
            user=recipient,
            subject=f"New application — {application.job.title}",
            template="new_application",
            category="application",
            context={
                "application": application,
                "job": application.job,
                "institution": application.job.institution,
                "candidate": application.candidate,
                "applicant_url": f"{settings.SITE_URL}{reverse('applications:recruiter_detail', args=[application.pk])}",
            },
        )


def update_application_status(application, new_status, actor, note="", request=None):
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    if new_status not in allowed:
        raise ApplicationError("That status change is not allowed for this application.")
    from_status = application.status
    if new_status == Application.Status.REJECTED and not note.strip():
        raise ApplicationError("Add a message for the candidate when marking as not selected.")
    with transaction.atomic():
        application.status = new_status
        application.status_updated_by = actor
        application.status_updated_at = timezone.now()
        application.save(update_fields=["status", "status_updated_by", "status_updated_at", "updated_at"])
        ApplicationStatusEvent.objects.create(
            application=application,
            from_status=from_status,
            to_status=new_status,
            actor=actor,
            note=note.strip(),
        )
    log_action(
        action="application.status_changed",
        summary=f"Application status changed: {application.job.title} → {new_status}",
        actor=actor,
        entity_type="application",
        entity_id=application.pk,
        metadata={"from": from_status, "to": new_status},
        request=request,
    )
    candidate = application.candidate
    notify_user(
        candidate,
        title=f"Application update — {application.job.title}",
        message=note.strip()
        or f"Your application status is now {application.get_status_display()}.",
        url=reverse("applications:candidate_detail", args=[application.pk]),
        category="application",
        level="success" if new_status == Application.Status.SELECTED else "info",
    )
    send_email(
        recipient=candidate.email,
        user=candidate,
        subject=f"Application update — {application.job.title}",
        template="application_status",
        category="application",
        context={
            "application": application,
            "job": application.job,
            "institution": application.job.institution,
            "status_label": application.get_status_display(),
            "note": note.strip(),
            "application_url": f"{settings.SITE_URL}{reverse('applications:candidate_detail', args=[application.pk])}",
        },
    )
    return application


def withdraw_application(application, candidate, request=None):
    if application.candidate_id != candidate.pk:
        raise ApplicationError("You can only withdraw your own application.")
    if application.status not in {
        Application.Status.SUBMITTED,
        Application.Status.UNDER_REVIEW,
        Application.Status.SHORTLISTED,
        Application.Status.SELECTED,
    }:
        raise ApplicationError("This application can no longer be withdrawn.")
    from_status = application.status
    with transaction.atomic():
        application.status = Application.Status.WITHDRAWN
        application.withdrawn_at = timezone.now()
        application.save(update_fields=["status", "withdrawn_at", "updated_at"])
        ApplicationStatusEvent.objects.create(
            application=application,
            from_status=from_status,
            to_status=Application.Status.WITHDRAWN,
            actor=candidate,
            note="Withdrawn by candidate",
        )
    log_action(
        action="application.withdrawn",
        summary=f"Application withdrawn: {application.job.title}",
        actor=candidate,
        entity_type="application",
        entity_id=application.pk,
        request=request,
    )
    for recruiter in application.job.institution.recruiters.filter(is_active=True).select_related("user"):
        notify_user(
            recruiter.user,
            title="Application withdrawn",
            message=f"{candidate.get_full_name()} withdrew their application for “{application.job.title}”.",
            url=reverse("applications:recruiter_detail", args=[application.pk]),
            category="application",
            level="warning",
        )
    return application


def add_internal_note(application, author, note):
    return ApplicationNote.objects.create(application=application, author=author, note=note.strip())


def record_external_click(request, job):
    from .models import ExternalApplicationClick

    session_key = request.session.session_key or ""
    session_hash = (
        hashlib.sha256(session_key.encode()).hexdigest() if session_key else ""
    )
    return ExternalApplicationClick.objects.create(
        job=job,
        user=request.user if request.user.is_authenticated else None,
        session_hash=session_hash,
    )
