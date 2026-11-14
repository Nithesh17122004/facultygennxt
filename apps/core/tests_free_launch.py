"""Free-launch regression tests.

These tests confirm that the core recruitment platform works end to end without
any payment, plan, subscription or paid-placement workflow, and that the retired
payment surface is no longer reachable.
"""
from pathlib import Path
from unittest.mock import patch

from django.apps import apps as django_apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import Application
from apps.applications.services import submit_application
from apps.core.testing import (
    PDF_BYTES,
    make_candidate,
    make_institution,
    make_job,
    make_recruiter,
    make_state_city,
    make_user,
)
from apps.documents.models import Document
from apps.institutions.models import Institution, Recruiter
from apps.jobs.models import Job, JobAlert
from apps.jobs.services import send_due_job_alerts, submit_job
from apps.notifications.models import EmailLog, Notification


class FreeLaunchMessagingTests(TestCase):
    def test_homepage_announces_free_academic_job_posting(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free Academic Job Posting for Educational Institutions.")
        self.assertContains(response, "Explore Academic Opportunities.")
        self.assertContains(response, "Register Your Institution — Free.")

    def test_institution_dashboard_states_free_services(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        self.client.force_login(recruiter)
        response = self.client.get(reverse("institutions:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "FacultyNxtGen currently provides free academic recruitment services to "
            "registered educational institutions.",
        )

    def test_public_pages_do_not_advertise_paid_plans(self):
        forbidden = [
            "Upgrade plan",
            "Buy premium",
            "Make payment",
            "Pay now",
            "View plans and pricing",
            "View plans",
            "Razorpay",
            "GST invoice",
            "Billing history",
        ]
        for url_name in [
            "core:home",
            "core:advertise",
            "core:about",
            "core:faq",
            "core:terms",
            "core:privacy",
            "core:contact",
        ]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)
            for phrase in forbidden:
                self.assertNotContains(response, phrase, msg_prefix=url_name)


class PaymentSurfaceRemovedTests(TestCase):
    def test_retired_payment_routes_are_not_reversible(self):
        for url_name in [
            "payments:plans",
            "payments:checkout",
            "payments:history",
            "payments:order_detail",
            "payments:webhook",
            "dashboard:payments",
            "dashboard:payment_detail",
            "dashboard:refund_decision",
        ]:
            with self.assertRaises(NoReverseMatch, msg=url_name):
                reverse(url_name)

    def test_payments_path_is_not_served(self):
        self.assertEqual(self.client.get("/payments/").status_code, 404)
        with self.assertRaises(Resolver404):
            resolve("/payments/")

    def test_payment_app_exposes_no_models_or_views(self):
        config = django_apps.get_app_config("payments")
        self.assertEqual(list(config.get_models()), [])
        self.assertFalse((Path(settings.BASE_DIR) / "apps" / "payments" / "views.py").exists())
        self.assertFalse((Path(settings.BASE_DIR) / "apps" / "payments" / "urls.py").exists())

    def test_no_payment_credentials_or_billing_settings_are_required(self):
        for setting_name in [
            "RAZORPAY_KEY_ID",
            "RAZORPAY_KEY_SECRET",
            "RAZORPAY_WEBHOOK_SECRET",
            "RAZORPAY_CURRENCY",
            "PAYMENTS_TEST_MODE",
            "PLATFORM_GSTIN",
            "PLATFORM_GST_RATE",
            "PLATFORM_BANK_DETAILS",
            "DEFAULT_CURRENCY",
        ]:
            self.assertFalse(hasattr(settings, setting_name), setting_name)

    def test_payment_category_is_not_a_notification_choice(self):
        self.assertNotIn("payment", Notification.Category.values)

    def test_paid_placement_fields_and_helpers_are_gone(self):
        job_fields = {field.name for field in Job._meta.get_fields()}
        self.assertNotIn("is_featured", job_fields)
        self.assertNotIn("featured_until", job_fields)

        institution_fields = {field.name for field in Institution._meta.get_fields()}
        self.assertNotIn("is_featured", institution_fields)
        self.assertFalse(hasattr(Institution, "active_subscription"))
        self.assertFalse(hasattr(Institution, "recruiter_limit"))

    def test_payment_templates_and_scripts_are_gone(self):
        base = Path(settings.BASE_DIR)
        self.assertFalse((base / "templates" / "payments").exists())
        self.assertFalse(
            (base / "templates" / "dashboard" / "admin" / "payments.html").exists()
        )
        self.assertFalse(
            (base / "templates" / "dashboard" / "admin" / "payment_detail.html").exists()
        )
        self.assertFalse((base / "static" / "js" / "payments.js").exists())


class FreeRecruitmentFlowTests(TestCase):
    def setUp(self):
        self.state, self.city = make_state_city()

    def test_candidate_registration_is_free(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Free Launch Candidate",
                "email": "free-candidate@example.com",
                "mobile": "9876500011",
                "password1": "SecurePass!2345",
                "password2": "SecurePass!2345",
                "terms": "on",
            },
        )
        self.assertRedirects(
            response, reverse("candidates:dashboard"), fetch_redirect_response=False
        )
        candidate = User.objects.get(email="free-candidate@example.com")
        self.assertEqual(candidate.role, User.Role.CANDIDATE)

    @patch("apps.institutions.views.create_document")
    def test_institution_registration_is_free(self, create_document):
        create_document.side_effect = lambda owner, **kwargs: Document.objects.create(
            owner=owner,
            original_name="authorisation.pdf",
            mime_type="application/pdf",
            size=len(PDF_BYTES),
            purpose=Document.Purpose.INSTITUTION_AUTHORIZATION,
        )
        response = self.client.post(
            reverse("institutions:register"),
            {
                "institution_name": "Free Launch Institute of Science",
                "website": "https://free.example.edu.in",
                "official_email": "registrar@free.example.edu.in",
                "contact_person": "Dr Free Launch",
                "contact_designation": "Registrar",
                "phone": "9880011999",
                "address": "1 Free Knowledge Road",
                "state": self.state.pk,
                "city": self.city.pk,
                "pincode": "500001",
                "institution_type": "engineering",
                "established_year": "2001",
                "password1": "SecurePass!2345",
                "password2": "SecurePass!2345",
                "authorization_document": SimpleUploadedFile(
                    "authorisation.pdf", PDF_BYTES, content_type="application/pdf"
                ),
                "terms": "on",
            },
        )
        self.assertRedirects(
            response, reverse("institutions:dashboard"), fetch_redirect_response=False
        )
        institution = Institution.objects.get(name="Free Launch Institute of Science")
        self.assertEqual(
            institution.verification_status, Institution.VerificationStatus.PENDING
        )
        self.assertTrue(
            Recruiter.objects.filter(institution=institution, is_primary=True).exists()
        )

    def test_verified_institution_publishes_without_payment(self):
        institution = make_institution(verified=False)
        recruiter = make_recruiter(institution=institution)
        staff = make_user(
            email="free-staff@example.com",
            full_name="Free Launch Reviewer",
            role=User.Role.ADMIN,
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])

        self.client.force_login(staff)
        response = self.client.post(
            reverse("dashboard:institution_decision", args=[institution.pk]),
            {
                "decision": Institution.VerificationStatus.VERIFIED,
                "notes": "Registration and authorisation documents verified.",
            },
        )
        self.assertRedirects(
            response,
            reverse("dashboard:institution_detail", args=[institution.pk]),
            fetch_redirect_response=False,
        )
        institution.refresh_from_db()
        self.assertTrue(institution.is_verified)
        self.assertIsNotNone(institution.verified_at)

        job = make_job(institution=institution, posted_by=recruiter)
        submit_job(job, recruiter)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PENDING)

        response = self.client.post(
            reverse("dashboard:job_decision", args=[job.pk]),
            {
                "form_name": "review",
                "action": "publish",
                "verified_institution": "on",
                "verified_recruiter": "on",
                "verified_advertisement": "on",
                "verified_application_url": "on",
                "verified_deadline": "on",
                "verified_eligibility": "on",
                "review_notes": "Published without any payment or paid plan.",
            },
        )
        self.assertRedirects(
            response,
            reverse("dashboard:job_detail", args=[job.pk]),
            fetch_redirect_response=False,
        )
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PUBLISHED)
        self.assertIsNotNone(job.published_at)
        self.assertEqual(self.client.get(job.get_absolute_url()).status_code, 200)

    @patch("apps.applications.services.create_document")
    def test_candidate_application_and_recruiter_review_are_free(self, create_document):
        create_document.side_effect = lambda owner, **kwargs: Document.objects.create(
            owner=owner,
            original_name="cv.pdf",
            mime_type="application/pdf",
            size=len(PDF_BYTES),
            purpose=Document.Purpose.APPLICATION_SUPPORT,
        )
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        job = make_job(
            institution=institution,
            posted_by=recruiter,
            status=Job.Status.PUBLISHED,
        )
        candidate = make_candidate(email="free-applicant@example.com", with_cv=False)
        application = submit_application(
            job=job,
            candidate=candidate,
            cover_letter="I would like to apply for this academic vacancy.",
            resume_file=SimpleUploadedFile(
                "cv.pdf", PDF_BYTES, content_type="application/pdf"
            ),
            attachment_files=[],
        )
        self.assertEqual(application.status, Application.Status.SUBMITTED)

        self.client.force_login(recruiter)
        response = self.client.post(
            reverse("applications:recruiter_detail", args=[application.pk]),
            {
                "update_status": "1",
                "status": Application.Status.UNDER_REVIEW,
                "note": "Your application is under review.",
            },
        )
        self.assertRedirects(
            response,
            reverse("applications:recruiter_detail", args=[application.pk]),
            fetch_redirect_response=False,
        )
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.UNDER_REVIEW)
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=candidate.email, template="application_status"
            ).exists()
        )

    def test_job_alerts_work_without_payment(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        job = make_job(
            institution=institution,
            posted_by=recruiter,
            status=Job.Status.PUBLISHED,
        )
        job.published_at = timezone.now()
        job.save(update_fields=["published_at"])

        candidate = make_candidate(email="alert-candidate@example.com", with_cv=False)
        JobAlert.objects.create(
            user=candidate,
            name="Computer Science roles",
            keyword="Computer Science",
            frequency=JobAlert.Frequency.DAILY,
        )
        sent = send_due_job_alerts()
        self.assertEqual(sent, 1)
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=candidate.email, template="job_alert"
            ).exists()
        )
