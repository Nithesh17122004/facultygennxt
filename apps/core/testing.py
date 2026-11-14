"""Small object factories shared by the test suite. Not used in production."""
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.core.models import City, State
from apps.documents.models import Document
from apps.institutions.models import Institution, Recruiter
from apps.jobs.models import Department, Designation, Job

PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


def make_user(*, email="candidate@example.com", full_name="Test Candidate", role=User.Role.CANDIDATE, verified=True, password="TestPass!2345"):
    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
    )
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def make_state_city():
    state, _ = State.objects.get_or_create(
        code="TS", defaults={"name": "Telangana", "slug": "telangana"}
    )
    city, _ = City.objects.get_or_create(
        state=state, slug="hyderabad", defaults={"name": "Hyderabad"}
    )
    return state, city


def make_institution(*, name="Test Institute of Technology", verified=True, user=None):
    state, city = make_state_city()
    institution = Institution.objects.create(
        name=name,
        website="https://example.edu.in",
        official_email="registrar@example.edu.in",
        phone="9876543210",
        contact_person="Registrar",
        contact_designation="Registrar",
        address="1 Knowledge Park",
        state=state,
        city=city,
        institution_type="engineering",
        verification_status=Institution.VerificationStatus.VERIFIED
        if verified
        else Institution.VerificationStatus.PENDING,
    )
    if verified:
        institution.verified_at = timezone.now()
        institution.save(update_fields=["verified_at"])
    return institution


def make_recruiter(*, institution, email="recruiter@example.edu.in", verified=True):
    user = make_user(
        email=email,
        full_name="Recruiter One",
        role=User.Role.RECRUITER,
        verified=verified,
    )
    Recruiter.objects.create(
        user=user,
        institution=institution,
        designation="HR Manager",
        is_primary=True,
        is_active=True,
    )
    return user


def make_job(
    *,
    institution,
    posted_by,
    title="Assistant Professor - Computer Science",
    status=Job.Status.DRAFT,
    application_method=Job.ApplicationMethod.INTERNAL,
    deadline_days=30,
):
    state, city = make_state_city()
    department, _ = Department.objects.get_or_create(
        slug="computer-science", defaults={"name": "Computer Science"}
    )
    designation, _ = Designation.objects.get_or_create(
        slug="assistant-professor", defaults={"name": "Assistant Professor"}
    )
    job = Job.objects.create(
        institution=institution,
        posted_by=posted_by,
        title=title,
        designation=designation,
        department=department,
        state=state,
        city=city,
        employment_type="full_time",
        description="Teach undergraduate and postgraduate computer science courses.",
        required_qualification="PhD in Computer Science or a closely related discipline.",
        eligibility="As per the official notification and UGC norms.",
        source_information="Official notification FNG/TEST/2026 dated 01 January 2026.",
        application_method=application_method,
        external_application_url="https://example.edu.in/careers"
        if application_method == Job.ApplicationMethod.EXTERNAL
        else "",
        deadline=timezone.localdate() + timedelta(days=deadline_days),
        publication_date=timezone.localdate(),
        status=status,
        notification_url="https://example.edu.in/notification.pdf",
    )
    return job


def make_candidate(*, email="applicant@example.com", verified=True, with_cv=True):
    user = make_user(email=email, full_name="Applicant One", verified=verified)
    profile, _ = CandidateProfile.objects.get_or_create(user=user)
    profile.headline = "Assistant Professor - Computer Science"
    profile.highest_qualification = "PhD in Computer Science"
    profile.phd_status = CandidateProfile.PhDStatus.COMPLETED
    profile.specialization = "Machine Learning"
    profile.save()
    if with_cv:
        document = Document.objects.create(
            owner=user,
            original_name="cv.pdf",
            mime_type="application/pdf",
            size=len(PDF_BYTES),
            purpose=Document.Purpose.CV,
            description="Test CV",
        )
        document.file.save("cv.pdf", ContentFile(PDF_BYTES), save=True)
        profile.cv = document
        profile.save(update_fields=["cv"])
    # The post_save signal may have cached the profile on the user instance;
    # keep that cache consistent with the values set above.
    user.candidate_profile = profile
    return user
