import shutil
import tempfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.applications.models import Application, ApplicationDocument
from apps.core.testing import (
    PDF_BYTES,
    make_candidate,
    make_institution,
    make_job,
    make_recruiter,
    make_user,
)
from apps.documents.models import Document, create_document
from apps.documents.services import build_download_url, user_can_access_document
from apps.documents.storage import private_storage
from apps.jobs.models import Job


def _pdf(name="cv.pdf"):
    return SimpleUploadedFile(name, PDF_BYTES, content_type="application/pdf")


class UploadValidationTests(TestCase):
    def test_pdf_signature_is_accepted(self):
        from apps.core.utils import validate_uploaded_document

        self.assertEqual(validate_uploaded_document(_pdf()), "application/pdf")

    def test_disallowed_extension_is_rejected(self):
        from apps.core.utils import validate_uploaded_document

        upload = SimpleUploadedFile("payload.exe", PDF_BYTES, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    def test_content_must_match_extension(self):
        from apps.core.utils import validate_uploaded_document

        upload = SimpleUploadedFile("cv.pdf", b"this is not a pdf", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    @override_settings(MAX_DOCUMENT_SIZE=32)
    def test_oversized_document_is_rejected(self):
        from apps.core.utils import validate_uploaded_document

        upload = SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)


class PrivateDocumentStorageTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fng-private-")
        self.original_location = private_storage._location
        private_storage._location = self.temp_dir
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)
        self.owner = make_user(email="owner@example.com")

    def tearDown(self):
        private_storage._location = self.original_location
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_document_records_metadata_and_private_path(self):
        document = create_document(
            owner=self.owner,
            uploaded_file=_pdf(),
            purpose=Document.Purpose.CV,
            description="Primary CV",
        )
        self.assertEqual(document.original_name, "cv.pdf")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertEqual(document.size, len(PDF_BYTES))
        self.assertTrue(document.checksum)
        self.assertTrue(document.file.name.startswith("private/"))
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertFalse(document.file.name.startswith("/"))

    def test_scan_failure_rejects_upload(self):
        with patch("apps.documents.models.scan_for_malware", return_value=False):
            with self.assertRaises(ValueError):
                create_document(
                    owner=self.owner,
                    uploaded_file=_pdf(),
                    purpose=Document.Purpose.CV,
                )


class SignedDownloadTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fng-download-")
        self.original_location = private_storage._location
        private_storage._location = self.temp_dir
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)
        self.owner = make_candidate(email="owner@example.com")
        self.document = self.owner.candidate_profile.cv

    def tearDown(self):
        private_storage._location = self.original_location
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_owner_can_download_with_signed_link(self):
        self.client.force_login(self.owner)
        response = self.client.get(build_download_url(self.document, self.owner))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)

    def test_another_user_cannot_reuse_owner_token(self):
        other = make_user(email="other@example.com")
        self.client.force_login(other)
        response = self.client.get(build_download_url(self.document, self.owner))
        self.assertEqual(response.status_code, 404)

    def test_another_user_with_own_token_is_forbidden(self):
        other = make_user(email="other@example.com")
        self.client.force_login(other)
        response = self.client.get(build_download_url(self.document, other))
        self.assertEqual(response.status_code, 403)

    def test_tampered_token_is_rejected(self):
        self.client.force_login(self.owner)
        url = build_download_url(self.document, self.owner)
        response = self.client.get(f"{url.split('?')[0]}?token=not-a-valid-token")
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(build_download_url(self.document, self.owner))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_deleted_document_cannot_be_downloaded(self):
        self.client.force_login(self.owner)
        url = build_download_url(self.document, self.owner)
        self.document.soft_delete()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_candidate_document(self):
        staff = make_user(email="staff@example.com")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        self.assertTrue(user_can_access_document(staff, self.document))
        self.client.force_login(staff)
        response = self.client.get(build_download_url(self.document, staff))
        self.assertEqual(response.status_code, 200)

    def test_recruiter_can_access_application_document(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        job = make_job(
            institution=institution,
            posted_by=recruiter,
            status=Job.Status.PUBLISHED,
        )
        application = Application.objects.create(
            job=job,
            candidate=self.owner,
            status=Application.Status.SUBMITTED,
        )
        ApplicationDocument.objects.create(
            application=application,
            document=self.document,
            label="CV",
        )
        self.assertTrue(user_can_access_document(recruiter, self.document))

        unrelated = make_recruiter(
            institution=make_institution(name="Another Institute"),
            email="unrelated@example.edu.in",
        )
        self.assertFalse(user_can_access_document(unrelated, self.document))


class DocumentDeletionTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="delete-owner@example.com")

    def test_owner_can_soft_delete_a_cv(self):
        document = Document.objects.create(
            owner=self.owner,
            original_name="cv.pdf",
            purpose=Document.Purpose.CV,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:delete", args=[document.pk]),
            {"next": reverse("candidates:documents")},
        )
        self.assertRedirects(response, reverse("candidates:documents"), fetch_redirect_response=False)
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)
        self.assertIsNotNone(document.deleted_at)

    def test_protected_institutional_document_cannot_be_deleted(self):
        document = Document.objects.create(
            owner=self.owner,
            original_name="authorisation.pdf",
            purpose=Document.Purpose.INSTITUTION_AUTHORIZATION,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:delete", args=[document.pk]),
            {"next": reverse("candidates:documents")},
        )
        self.assertRedirects(response, reverse("candidates:documents"), fetch_redirect_response=False)
        document.refresh_from_db()
        self.assertFalse(document.is_deleted)
