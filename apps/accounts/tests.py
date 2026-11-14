from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.testing import make_institution, make_recruiter, make_user
from apps.notifications.models import EmailLog

from .tokens import email_verification_token

User = get_user_model()


class CandidateRegistrationTests(TestCase):
    def test_registration_creates_unverified_candidate_and_sends_verification(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Asha Rao",
                "email": "asha@example.com",
                "mobile": "9876543210",
                "password1": "SecurePass!2345",
                "password2": "SecurePass!2345",
                "terms": "on",
            },
        )
        self.assertRedirects(response, reverse("candidates:dashboard"), fetch_redirect_response=False)
        user = User.objects.get(email="asha@example.com")
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertIsNone(user.email_verified_at)
        log = EmailLog.objects.get(recipient_email="asha@example.com", template="verify_email")
        self.assertIn(log.status, {EmailLog.Status.SENT, EmailLog.Status.QUEUED})
        self.assertIn("verify-email", log.rendered_html)
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_duplicate_email_is_rejected(self):
        make_user(email="existing@example.com")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Existing",
                "email": "existing@example.com",
                "mobile": "9876543211",
                "password1": "SecurePass!2345",
                "password2": "SecurePass!2345",
                "terms": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)


class RegistrationRateLimitTests(TestCase):
    def test_rate_limited_registration_returns_friendly_429(self):
        cache.clear()
        url = reverse("accounts:register")
        invalid_payload = {
            "full_name": "Rate Limited",
            "email": "rate-limited@example.com",
            "mobile": "9876543299",
            "password1": "SecurePass!2345",
            "password2": "SecurePass!2345",
            # Terms intentionally omitted so each attempt is a validation error.
        }
        for _ in range(6):
            response = self.client.post(
                url, invalid_payload, REMOTE_ADDR="203.0.113.77"
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url, invalid_payload, REMOTE_ADDR="203.0.113.77"
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many requests", status_code=429)
        self.assertEqual(response["Retry-After"], "60")
        self.assertNotContains(
            response, "You do not have access to this page", status_code=429
        )


class EmailVerificationTests(TestCase):
    def test_valid_token_verifies_email_and_sends_welcome(self):
        user = make_user(email="verify@example.com", verified=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        response = self.client.get(
            reverse("accounts:verify_email", args=[uid, token]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(
            EmailLog.objects.filter(recipient_email=user.email, template="welcome").exists()
        )

    def test_invalid_token_is_rejected(self):
        user = make_user(email="invalid@example.com", verified=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        response = self.client.get(
            reverse("accounts:verify_email", args=[uid, "invalid-token"])
        )
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertIsNone(user.email_verified_at)


@override_settings(LOGIN_MAX_FAILED_ATTEMPTS=2, LOGIN_LOCKOUT_MINUTES=15)
class LoginSecurityTests(TestCase):
    def setUp(self):
        self.user = make_user(email="login@example.com", password="CorrectPass!2345")

    def test_repeated_failures_lock_the_account(self):
        for _ in range(2):
            self.client.post(
                reverse("accounts:login"),
                {"email": "login@example.com", "password": "WrongPass!2345"},
            )
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.locked_until)

    def test_correct_password_after_lock_is_rejected(self):
        for _ in range(2):
            self.client.post(
                reverse("accounts:login"),
                {"email": "login@example.com", "password": "WrongPass!2345"},
            )
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "login@example.com", "password": "CorrectPass!2345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporarily locked")
        self.assertNotIn("_auth_user_id", self.client.session)


class RolePermissionTests(TestCase):
    def test_candidate_cannot_open_institution_dashboard(self):
        make_user(email="candidate@example.com")
        self.client.force_login(User.objects.get(email="candidate@example.com"))
        response = self.client.get(reverse("institutions:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_recruiter_cannot_open_platform_admin_dashboard(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        self.client.force_login(recruiter)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 403)

    def test_unverified_recruiter_is_sent_to_verification(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution, verified=False)
        self.client.force_login(recruiter)
        response = self.client.get(reverse("institutions:dashboard"))
        self.assertRedirects(response, reverse("accounts:verify_email_pending"))
