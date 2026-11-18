from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import City, State
from apps.core.testing import PDF_BYTES, make_candidate, make_institution, make_recruiter
from apps.documents.models import Document
from apps.institutions.models import Institution, InstitutionDocument, Recruiter


class InstitutionRegistrationTests(TestCase):
    def setUp(self):
        self.state = State.objects.create(name="Karnataka", slug="karnataka", code="KA")
        self.city = City.objects.create(state=self.state, name="Bengaluru", slug="bengaluru")

    def test_registration_city_options_match_state_select_value(self):
        response = self.client.get(reverse("institutions:register"))
        self.assertContains(response, 'data-state="%s"' % self.state.pk)
        self.assertContains(response, "Bengaluru")

    def _document(self, owner, **kwargs):
        return Document.objects.create(
            owner=owner,
            original_name="authorisation.pdf",
            mime_type="application/pdf",
            size=len(PDF_BYTES),
            purpose=Document.Purpose.INSTITUTION_AUTHORIZATION,
            **kwargs,
        )

    @patch("apps.institutions.views.create_document")
    def test_registration_creates_pending_institution_and_primary_recruiter(self, create_document):
        create_document.side_effect = lambda owner, **kwargs: self._document(owner)
        response = self.client.post(
            reverse("institutions:register"),
            {
                "institution_name": "Bengaluru Institute of Science",
                "website": "https://bisc.example.edu.in",
                "official_email": "registrar@bisc.example.edu.in",
                "contact_person": "Dr Meera Iyer",
                "contact_designation": "Registrar",
                "phone": "9880011223",
                "address": "100 Science Road, Bengaluru",
                "state": self.state.pk,
                "city": self.city.pk,
                "pincode": "560001",
                "institution_type": "engineering",
                "established_year": "1998",
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
        institution = Institution.objects.get(name="Bengaluru Institute of Science")
        self.assertEqual(institution.verification_status, Institution.VerificationStatus.PENDING)
        self.assertTrue(Recruiter.objects.filter(institution=institution, is_primary=True).exists())
        self.assertTrue(InstitutionDocument.objects.filter(institution=institution).exists())

    def test_duplicate_institution_name_is_rejected(self):
        make_institution(name="Existing Institute", verified=False)
        response = self.client.post(
            reverse("institutions:register"),
            {
                "institution_name": "Existing Institute",
                "website": "https://other.example.edu.in",
                "official_email": "registrar@other.example.edu.in",
                "contact_person": "Registrar",
                "contact_designation": "Registrar",
                "phone": "9880011224",
                "address": "Somewhere",
                "state": self.state.pk,
                "city": self.city.pk,
                "institution_type": "private",
                "password1": "SecurePass!2345",
                "password2": "SecurePass!2345",
                "authorization_document": SimpleUploadedFile(
                    "authorisation.pdf", PDF_BYTES, content_type="application/pdf"
                ),
                "terms": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already registered")


class InstitutionVerificationGateTests(TestCase):
    def test_primary_recruiter_can_be_resolved_for_verified_institution(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        from apps.institutions.models import institution_for_user

        self.assertEqual(institution_for_user(recruiter), institution)

    def test_candidate_cannot_create_a_vacancy(self):
        candidate = make_candidate()
        self.client.force_login(candidate)
        response = self.client.get(reverse("jobs:recruiter_create"))
        self.assertEqual(response.status_code, 403)

    def test_unverified_recruiter_is_blocked_from_creating_vacancies(self):
        institution = make_institution(verified=False)
        recruiter = make_recruiter(institution=institution)
        self.client.force_login(recruiter)
        response = self.client.get(reverse("jobs:recruiter_create"))
        self.assertRedirects(response, reverse("institutions:profile"))

    def test_institution_verification_decision_sets_timestamp(self):
        institution = make_institution(verified=False)
        institution.verification_status = Institution.VerificationStatus.VERIFIED
        institution.verified_at = timezone.now()
        institution.save(update_fields=["verification_status", "verified_at"])
        institution.refresh_from_db()
        self.assertTrue(institution.is_verified)
