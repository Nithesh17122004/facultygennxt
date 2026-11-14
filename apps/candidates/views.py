import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import candidate_required
from apps.audit.services import log_action
from apps.core.constants import EMPLOYMENT_TYPES
from apps.core.models import City, State
from apps.documents.models import Document
from apps.documents.services import create_document
from apps.notifications.models import EmailPreference
from apps.notifications.services import notify_user
from apps.jobs.models import JobAlert, SavedJob
from apps.jobs.services import recommend_jobs

from .forms import (
    CandidateDocumentUploadForm,
    CandidatePrivacyForm,
    CandidateProfileForm,
    CertificationForm,
    PublicationForm,
    QualificationForm,
    ResearchExperienceForm,
    TeachingExperienceForm,
)
from .models import (
    CandidateProfile,
    Certification,
    Publication,
    Qualification,
    ResearchExperience,
    TeachingExperience,
)

logger = logging.getLogger("facultynxtgen.candidates")


def _profile(request):
    profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
    return profile


@candidate_required
def dashboard(request):
    profile = _profile(request)
    applications = request.user.applications.select_related("job__institution").order_by("-applied_at")
    saved_count = request.user.saved_jobs.count()
    active_alerts = request.user.job_alerts.filter(is_active=True).count()
    recommended = recommend_jobs(profile, limit=6)
    completed_sections = sum(
        [
            bool(profile.headline and profile.specialization),
            bool(profile.qualifications.exists()),
            bool(profile.teaching_experiences.exists() or profile.research_experiences.exists()),
            bool(profile.cv_id and not profile.cv.is_deleted),
            bool(profile.department_id or profile.preferred_designation_id),
        ]
    )
    tasks = []
    if not request.user.is_email_verified:
        tasks.append(
            {
                "title": "Verify your email address",
                "copy": "Verification is required before applying to vacancies.",
                "url": "accounts:verify_email_pending",
                "icon": "envelope-check",
            }
        )
    if not profile.cv_id or profile.cv.is_deleted:
        tasks.append(
            {
                "title": "Upload your CV",
                "copy": "Keep an updated PDF ready for one-click applications.",
                "url": "candidates:documents",
                "icon": "file-earmark-pdf",
            }
        )
    if not profile.qualifications.exists():
        tasks.append(
            {
                "title": "Add your qualifications",
                "copy": "Recruiters need your academic record to assess eligibility.",
                "url": "candidates:qualifications",
                "icon": "mortarboard",
            }
        )
    if not profile.department_id:
        tasks.append(
            {
                "title": "Choose your department",
                "copy": "This powers relevant job recommendations.",
                "url": "candidates:profile",
                "icon": "diagram-3",
            }
        )
    return render(
        request,
        "candidates/dashboard.html",
        {
            "profile": profile,
            "applications": applications[:5],
            "application_count": applications.count(),
            "shortlisted_count": applications.filter(status="shortlisted").count(),
            "saved_count": saved_count,
            "active_alerts": active_alerts,
            "recommended_jobs": recommended,
            "completed_sections": completed_sections,
            "tasks": tasks,
        },
    )


@candidate_required
def profile_view(request):
    profile = _profile(request)
    form = CandidateProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        old_avatar = profile.avatar.name if profile.avatar else ""
        profile = form.save()
        if old_avatar and profile.avatar and old_avatar != profile.avatar.name:
            profile.avatar.storage.delete(old_avatar)
        log_action(
            action="candidate.profile_updated",
            summary="Academic profile updated",
            actor=request.user,
            entity_type="candidate_profile",
            entity_id=profile.pk,
            request=request,
        )
        messages.success(request, "Your academic profile has been updated.")
        return redirect("candidates:profile")
    completion = profile.completion_percentage
    return render(
        request,
        "candidates/profile.html",
        {"form": form, "profile": profile, "completion": completion},
    )


@candidate_required
def privacy(request):
    profile = _profile(request)
    preference, _ = EmailPreference.objects.get_or_create(user=request.user)
    form = CandidatePrivacyForm(
        request.POST or None, profile=profile, preference=preference
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(
            action="candidate.privacy_updated",
            summary="Candidate privacy preferences updated",
            actor=request.user,
            entity_type="candidate_profile",
            entity_id=profile.pk,
            request=request,
        )
        messages.success(request, "Your privacy preferences have been saved.")
        return redirect("candidates:privacy")
    return render(
        request,
        "candidates/privacy.html",
        {"form": form, "profile": profile, "preference": preference},
    )


@candidate_required
def settings_view(request):
    from apps.accounts.forms import AccountIdentityForm

    form = AccountIdentityForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your account details have been updated.")
        return redirect("candidates:settings")
    return render(
        request,
        "candidates/settings.html",
        {"form": form, "profile": _profile(request)},
    )


@candidate_required
def qualifications(request):
    profile = _profile(request)
    form = QualificationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        qualification = form.save(commit=False)
        qualification.profile = profile
        if form.cleaned_data.get("document_file"):
            document = create_document(
                owner=request.user,
                uploaded_file=form.cleaned_data["document_file"],
                purpose=Document.Purpose.CERTIFICATE,
                description=f"Qualification certificate — {qualification.degree}",
            )
            qualification.document = document
        qualification.save()
        log_action(
            action="candidate.qualification_added",
            summary=f"Qualification added: {qualification.degree}",
            actor=request.user,
            entity_type="qualification",
            entity_id=qualification.pk,
            request=request,
        )
        messages.success(request, "Qualification added.")
        return redirect("candidates:qualifications")
    return render(
        request,
        "candidates/qualifications.html",
        {"records": profile.qualifications.select_related("document"), "form": form},
    )


@candidate_required
def qualification_edit(request, pk):
    profile = _profile(request)
    record = get_object_or_404(Qualification, pk=pk, profile=profile)
    form = QualificationForm(request.POST or None, request.FILES or None, instance=record)
    if request.method == "POST" and form.is_valid():
        qualification = form.save(commit=False)
        if form.cleaned_data.get("document_file"):
            document = create_document(
                owner=request.user,
                uploaded_file=form.cleaned_data["document_file"],
                purpose=Document.Purpose.CERTIFICATE,
                description=f"Qualification certificate — {qualification.degree}",
            )
            qualification.document = document
        qualification.save()
        messages.success(request, "Qualification updated.")
        return redirect("candidates:qualifications")
    return render(
        request,
        "candidates/qualification_form.html",
        {"form": form, "record": record},
    )


@candidate_required
@require_POST
def qualification_delete(request, pk):
    record = get_object_or_404(Qualification, pk=pk, profile=_profile(request))
    record.delete()
    messages.success(request, "Qualification removed.")
    return redirect("candidates:qualifications")


@candidate_required
def teaching_experience(request):
    profile = _profile(request)
    form = TeachingExperienceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.profile = profile
        record.full_clean()
        record.save()
        messages.success(request, "Teaching experience added.")
        return redirect("candidates:teaching_experience")
    return render(
        request,
        "candidates/teaching_experience.html",
        {"records": profile.teaching_experiences.all(), "form": form},
    )


@candidate_required
def teaching_experience_edit(request, pk):
    record = get_object_or_404(TeachingExperience, pk=pk, profile=_profile(request))
    form = TeachingExperienceForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Teaching experience updated.")
        return redirect("candidates:teaching_experience")
    return render(request, "candidates/simple_record_form.html", {"form": form, "title": "Edit teaching experience"})


@candidate_required
@require_POST
def teaching_experience_delete(request, pk):
    get_object_or_404(TeachingExperience, pk=pk, profile=_profile(request)).delete()
    messages.success(request, "Teaching experience removed.")
    return redirect("candidates:teaching_experience")


@candidate_required
def research_experience(request):
    profile = _profile(request)
    form = ResearchExperienceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.profile = profile
        record.full_clean()
        record.save()
        messages.success(request, "Research experience added.")
        return redirect("candidates:research_experience")
    return render(
        request,
        "candidates/research_experience.html",
        {"records": profile.research_experiences.all(), "form": form},
    )


@candidate_required
def research_experience_edit(request, pk):
    record = get_object_or_404(ResearchExperience, pk=pk, profile=_profile(request))
    form = ResearchExperienceForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Research experience updated.")
        return redirect("candidates:research_experience")
    return render(request, "candidates/simple_record_form.html", {"form": form, "title": "Edit research experience"})


@candidate_required
@require_POST
def research_experience_delete(request, pk):
    get_object_or_404(ResearchExperience, pk=pk, profile=_profile(request)).delete()
    messages.success(request, "Research experience removed.")
    return redirect("candidates:research_experience")


@candidate_required
def publications(request):
    profile = _profile(request)
    form = PublicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.profile = profile
        record.save()
        messages.success(request, "Publication added.")
        return redirect("candidates:publications")
    return render(
        request,
        "candidates/publications.html",
        {"records": profile.publications.all(), "form": form},
    )


@candidate_required
def publication_edit(request, pk):
    record = get_object_or_404(Publication, pk=pk, profile=_profile(request))
    form = PublicationForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Publication updated.")
        return redirect("candidates:publications")
    return render(request, "candidates/simple_record_form.html", {"form": form, "title": "Edit publication"})


@candidate_required
@require_POST
def publication_delete(request, pk):
    get_object_or_404(Publication, pk=pk, profile=_profile(request)).delete()
    messages.success(request, "Publication removed.")
    return redirect("candidates:publications")


@candidate_required
def certifications(request):
    profile = _profile(request)
    form = CertificationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.profile = profile
        if form.cleaned_data.get("document_file"):
            record.document = create_document(
                owner=request.user,
                uploaded_file=form.cleaned_data["document_file"],
                purpose=Document.Purpose.CERTIFICATE,
                description=f"Certification — {record.name}",
            )
        record.save()
        messages.success(request, "Certification added.")
        return redirect("candidates:certifications")
    return render(
        request,
        "candidates/certifications.html",
        {"records": profile.certifications.select_related("document"), "form": form},
    )


@candidate_required
def certification_edit(request, pk):
    record = get_object_or_404(Certification, pk=pk, profile=_profile(request))
    form = CertificationForm(request.POST or None, request.FILES or None, instance=record)
    if request.method == "POST" and form.is_valid():
        certification = form.save(commit=False)
        if form.cleaned_data.get("document_file"):
            certification.document = create_document(
                owner=request.user,
                uploaded_file=form.cleaned_data["document_file"],
                purpose=Document.Purpose.CERTIFICATE,
                description=f"Certification — {certification.name}",
            )
        certification.save()
        messages.success(request, "Certification updated.")
        return redirect("candidates:certifications")
    return render(request, "candidates/simple_record_form.html", {"form": form, "title": "Edit certification"})


@candidate_required
@require_POST
def certification_delete(request, pk):
    get_object_or_404(Certification, pk=pk, profile=_profile(request)).delete()
    messages.success(request, "Certification removed.")
    return redirect("candidates:certifications")


@candidate_required
def documents(request):
    profile = _profile(request)
    form = CandidateDocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = create_document(
            owner=request.user,
            uploaded_file=form.cleaned_data["file"],
            purpose=form.cleaned_data["purpose"],
            description=form.cleaned_data.get("description", ""),
        )
        if document.purpose == Document.Purpose.CV:
            profile.cv = document
            profile.save(update_fields=["cv", "updated_at"])
        notify_user(
            request.user,
            title="Document uploaded",
            message=f"{document.original_name} was added securely. It remains private to you and recruiters you apply to.",
            url="/dashboard/candidate/documents/",
            category="account",
            level="success",
        )
        messages.success(
            request,
            "Your document was uploaded. It is stored privately and only shared when you apply.",
        )
        return redirect("candidates:documents")
    documents_qs = request.user.documents.filter(is_deleted=False).select_related("owner")
    return render(
        request,
        "candidates/documents.html",
        {"form": form, "documents": documents_qs, "profile": profile},
    )


@candidate_required
def saved_jobs(request):
    saved = (
        SavedJob.objects.filter(user=request.user)
        .select_related("job", "job__institution", "job__designation", "job__department")
        .order_by("-created_at")
    )
    paginator = Paginator(saved, 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "candidates/saved_jobs.html", {"page_obj": page, "saved_count": saved.count()})


@candidate_required
def job_alerts(request):
    alerts = request.user.job_alerts.select_related("department", "designation", "state", "city")
    return render(request, "candidates/job_alerts.html", {"alerts": alerts})


@candidate_required
def job_alert_create(request):
    from apps.jobs.forms import JobAlertForm

    if request.user.job_alerts.filter(is_active=True).count() >= 10:
        messages.warning(request, "You can keep up to 10 active alerts. Pause or remove one first.")
        return redirect("candidates:job_alerts")
    form = JobAlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        alert = form.save(commit=False)
        alert.user = request.user
        alert.save()
        messages.success(
            request,
            "Job alert created. We will email matching jobs according to your preferences.",
        )
        return redirect("candidates:job_alerts")
    return render(
        request,
        "candidates/job_alert_form.html",
        {
            "form": form,
            "states": State.objects.filter(is_active=True),
            "cities": City.objects.filter(is_active=True).select_related("state"),
            "employment_types": EMPLOYMENT_TYPES,
            "title": "Create a job alert",
        },
    )


@candidate_required
def job_alert_edit(request, pk):
    from apps.jobs.forms import JobAlertForm

    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    form = JobAlertForm(request.POST or None, instance=alert)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Job alert updated.")
        return redirect("candidates:job_alerts")
    return render(
        request,
        "candidates/job_alert_form.html",
        {
            "form": form,
            "states": State.objects.filter(is_active=True),
            "cities": City.objects.filter(is_active=True).select_related("state"),
            "employment_types": EMPLOYMENT_TYPES,
            "title": "Edit job alert",
            "alert": alert,
        },
    )


@candidate_required
@require_POST
def job_alert_toggle(request, pk):
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.is_active = not alert.is_active
    alert.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request, f"Alert {'resumed' if alert.is_active else 'paused'}."
    )
    return redirect("candidates:job_alerts")


@candidate_required
@require_POST
def job_alert_delete(request, pk):
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.delete()
    messages.success(request, "Job alert deleted.")
    return redirect("candidates:job_alerts")


@candidate_required
def recommended_jobs(request):
    profile = _profile(request)
    recommended = recommend_jobs(profile, limit=24)
    return render(
        request,
        "candidates/recommended_jobs.html",
        {"jobs": recommended, "profile": profile},
    )
