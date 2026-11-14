from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import make_institution, make_job, make_recruiter
from apps.jobs.models import Job
from apps.jobs.services import (
    JobWorkflowError,
    approve_job,
    publish_job,
    reject_job,
    submit_job,
    update_verification_checklist,
)
from apps.notifications.models import EmailLog


class JobWorkflowTests(TestCase):
    def setUp(self):
        self.institution = make_institution()
        self.recruiter = make_recruiter(institution=self.institution)
        self.job = make_job(institution=self.institution, posted_by=self.recruiter)

    def _complete_checklist(self):
        update_verification_checklist(
            self.job,
            {
                "verified_institution": True,
                "verified_recruiter": True,
                "verified_advertisement": True,
                "verified_application_url": True,
                "verified_deadline": True,
                "verified_eligibility": True,
                "review_notes": "Official notification checked.",
            },
            actor=self.recruiter,
        )

    def test_submit_requires_verified_institution(self):
        self.institution.verification_status = self.institution.VerificationStatus.PENDING
        self.institution.save(update_fields=["verification_status"])
        with self.assertRaises(JobWorkflowError):
            submit_job(self.job, self.recruiter)

    def test_complete_draft_can_be_submitted_reviewed_and_published(self):
        submit_job(self.job, self.recruiter)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PENDING)
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=self.recruiter.email, template="job_submitted"
            ).exists()
        )

        self._complete_checklist()
        approve_job(self.job, self.recruiter)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.APPROVED)

        publish_job(self.job, self.recruiter)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PUBLISHED)
        self.assertIsNotNone(self.job.published_at)
        self.assertTrue(self.job.is_live)

    def test_publish_without_checklist_is_blocked(self):
        self.job.status = Job.Status.PENDING
        self.job.save(update_fields=["status"])
        with self.assertRaises(JobWorkflowError):
            publish_job(self.job, self.recruiter)

    def test_reject_requires_reason_and_notifies_institution(self):
        self.job.status = Job.Status.PENDING
        self.job.save(update_fields=["status"])
        with self.assertRaises(JobWorkflowError):
            reject_job(self.job, self.recruiter, " ")
        reject_job(self.job, self.recruiter, "The notification PDF is missing.")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.REJECTED)
        self.assertIn("notification", self.job.rejection_reason.lower())
        self.assertTrue(
            EmailLog.objects.filter(
                recipient_email=self.recruiter.email, template="job_rejected"
            ).exists()
        )

    def test_incomplete_draft_cannot_be_submitted(self):
        self.job.description = ""
        self.job.save(update_fields=["description"])
        with self.assertRaises(JobWorkflowError):
            submit_job(self.job, self.recruiter)


class PublicJobVisibilityTests(TestCase):
    def setUp(self):
        self.institution = make_institution()
        self.recruiter = make_recruiter(institution=self.institution)
        self.published = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            title="Published Physics Vacancy",
            status=Job.Status.PUBLISHED,
        )
        self.draft = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            title="Confidential Draft Vacancy",
            status=Job.Status.DRAFT,
        )

    def test_find_jobs_lists_only_published_vacancies(self):
        response = self.client.get(reverse("jobs:find"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Physics Vacancy")
        self.assertNotContains(response, "Confidential Draft Vacancy")

    def test_published_detail_has_json_ld(self):
        response = self.client.get(self.published.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JobPosting")
        self.assertContains(response, "application/ld+json")

    def test_draft_detail_is_not_public(self):
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_expired_vacancy_returns_gone(self):
        self.published.publication_date = timezone.localdate() - timedelta(days=60)
        self.published.deadline = timezone.localdate() - timedelta(days=1)
        self.published.save(update_fields=["publication_date", "deadline"])
        response = self.client.get(self.published.get_absolute_url())
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "no longer accepting", status_code=410)

    def test_external_job_detail_discloses_official_application_route(self):
        external = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            title="External Application Vacancy",
            status=Job.Status.PUBLISHED,
            application_method=Job.ApplicationMethod.EXTERNAL,
        )
        response = self.client.get(external.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "official")
        self.assertContains(response, "external application")
        self.assertContains(response, external.external_application_url)
