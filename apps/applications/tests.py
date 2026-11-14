from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.applications.models import Application
from apps.applications.services import (
    ApplicationError,
    submit_application,
    update_application_status,
)
from apps.core.testing import PDF_BYTES, make_candidate, make_institution, make_job, make_recruiter
from apps.documents.models import Document
from apps.jobs.models import Job
from apps.notifications.models import EmailLog


class ApplicationSubmissionTests(TestCase):
    def setUp(self):
        self.institution = make_institution()
        self.recruiter = make_recruiter(institution=self.institution)
        self.job = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            status=Job.Status.PUBLISHED,
        )

    def _fake_document(self, owner, **kwargs):
        return Document.objects.create(
            owner=owner,
            original_name="cv.pdf",
            mime_type="application/pdf",
            purpose=Document.Purpose.APPLICATION_SUPPORT,
        )

    def test_unverified_candidate_cannot_apply(self):
        candidate = make_candidate(email="unverified@example.com", verified=False, with_cv=False)
        with self.assertRaises(ApplicationError):
            submit_application(
                job=self.job,
                candidate=candidate,
                cover_letter="I am interested.",
                resume_file=SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
                attachment_files=[],
            )

    @patch("apps.applications.services.create_document")
    def test_verified_candidate_can_apply_once(self, create_document):
        create_document.side_effect = self._fake_document
        candidate = make_candidate(email="verified@example.com", with_cv=False)
        application = submit_application(
            job=self.job,
            candidate=candidate,
            cover_letter="I have relevant teaching experience.",
            resume_file=SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
            attachment_files=[],
        )
        self.assertEqual(application.status, Application.Status.SUBMITTED)
        self.assertTrue(application.profile_snapshot)
        self.assertTrue(application.documents.exists())
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=candidate.email, template="application_received"
            ).exists()
        )
        with self.assertRaises(ApplicationError):
            submit_application(
                job=self.job,
                candidate=candidate,
                cover_letter="Duplicate",
                resume_file=SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
                attachment_files=[],
            )

    def test_external_job_cannot_be_applied_through_platform(self):
        external = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            status=Job.Status.PUBLISHED,
            application_method=Job.ApplicationMethod.EXTERNAL,
        )
        candidate = make_candidate(email="external@example.com", with_cv=False)
        with self.assertRaises(ApplicationError):
            submit_application(
                job=external,
                candidate=candidate,
                cover_letter="",
                resume_file=SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
                attachment_files=[],
            )


class ApplicationWorkflowTests(TestCase):
    def setUp(self):
        self.institution = make_institution()
        self.recruiter = make_recruiter(institution=self.institution)
        self.job = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            status=Job.Status.PUBLISHED,
        )
        self.candidate = make_candidate(email="workflow@example.com", with_cv=False)
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            status=Application.Status.SUBMITTED,
        )

    def test_invalid_status_transition_is_rejected(self):
        with self.assertRaises(ApplicationError):
            update_application_status(
                self.application, Application.Status.SELECTED, actor=self.recruiter
            )

    def test_valid_transition_notifies_candidate(self):
        update_application_status(
            self.application,
            Application.Status.UNDER_REVIEW,
            actor=self.recruiter,
            note="Your application is being reviewed.",
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.UNDER_REVIEW)
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=self.candidate.email, template="application_status"
            ).exists()
        )

    def test_other_institution_recruiter_cannot_view_application(self):
        other_institution = make_institution(name="Other Institute")
        other_recruiter = make_recruiter(
            institution=other_institution, email="other-recruiter@example.edu.in"
        )
        self.client.force_login(other_recruiter)
        response = self.client.get(
            reverse("applications:recruiter_detail", args=[self.application.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_recruiter_can_view_application(self):
        self.client.force_login(self.recruiter)
        response = self.client.get(
            reverse("applications:recruiter_detail", args=[self.application.pk])
        )
        self.assertEqual(response.status_code, 200)
