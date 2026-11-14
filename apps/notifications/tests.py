from django.core import mail, signing
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ContactEnquiry
from apps.core.testing import make_user
from apps.notifications.models import EmailLog, EmailPreference, Notification
from apps.notifications.services import notify_staff, notify_user, send_email


class EmailDispatchTests(TestCase):
    def setUp(self):
        self.user = make_user(email="email@example.com", verified=True)
        self.enquiry = ContactEnquiry.objects.create(
            name="Asha Rao",
            email="asha@example.com",
            purpose=ContactEnquiry.Purpose.GENERAL,
            subject="Verification question",
            message="Could you explain how institution verification works?",
            consent=True,
        )

    def _send_contact_email(self, **kwargs):
        category = kwargs.pop("category", "transactional")
        return send_email(
            recipient="asha@example.com",
            subject="We received your enquiry",
            template="contact_received",
            category=category,
            context={
                "enquiry": self.enquiry,
                "reference": str(self.enquiry.reference)[:8].upper(),
            },
            **kwargs,
        )

    def test_rendered_bodies_are_persisted_and_delivered(self):
        log = self._send_contact_email()
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.attempts, 1)
        self.assertIn("We received your enquiry", log.rendered_html)
        self.assertIn("Verification question", log.rendered_html)
        self.assertIn("Verification question", log.rendered_text)
        self.assertTrue(log.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("asha@example.com", mail.outbox[0].to)

    def test_missing_template_marks_log_failed(self):
        log = send_email(
            recipient="asha@example.com",
            subject="Missing",
            template="template_that_does_not_exist",
        )
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertIn("missing", log.error.lower())
        self.assertEqual(log.rendered_html, "")
        self.assertEqual(len(mail.outbox), 0)

    def test_marketing_email_is_suppressed_without_opt_in(self):
        EmailPreference.objects.create(user=self.user, marketing=False)
        log = self._send_contact_email(user=self.user, category="marketing")
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SUPPRESSED)
        self.assertEqual(log.rendered_html, "")
        self.assertEqual(len(mail.outbox), 0)

    def test_marketing_email_is_sent_after_opt_in(self):
        preference, _ = EmailPreference.objects.get_or_create(user=self.user)
        preference.marketing = True
        preference.save(update_fields=["marketing", "updated_at"])
        log = self._send_contact_email(user=self.user, category="marketing")
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_application_preferences_control_application_mail(self):
        preference, _ = EmailPreference.objects.get_or_create(user=self.user)
        preference.application_updates = False
        preference.save(update_fields=["application_updates", "updated_at"])
        log = self._send_contact_email(user=self.user, category="application")
        log.refresh_from_db()
        self.assertEqual(log.status, EmailLog.Status.SUPPRESSED)

    def test_blank_recipient_is_ignored(self):
        self.assertIsNone(
            send_email(recipient="  ", subject="No one", template="contact_received")
        )
        self.assertEqual(EmailLog.objects.count(), 0)

    def test_preference_category_mapping(self):
        preference = EmailPreference(user=self.user)
        self.assertTrue(preference.allows("transactional"))
        self.assertFalse(preference.allows("marketing"))
        self.assertTrue(preference.allows("job_alert"))
        self.assertTrue(preference.allows("application"))
        self.assertTrue(preference.allows("institution"))


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = make_user(email="notify@example.com")

    def test_notify_user_creates_unread_notification(self):
        notification = notify_user(
            self.user,
            title="Application received",
            message="Your application was submitted.",
            url="/applications/",
            category=Notification.Category.APPLICATION,
        )
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        notification.mark_read()
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_notify_staff_reaches_only_active_staff(self):
        staff = make_user(email="staff@example.com")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        inactive_staff = make_user(email="inactive-staff@example.com")
        inactive_staff.is_staff = True
        inactive_staff.is_active = False
        inactive_staff.save(update_fields=["is_staff", "is_active"])

        notify_staff("Institution pending", "A new institution needs review.", "/dashboard/")

        self.assertTrue(
            Notification.objects.filter(
                recipient=staff, category=Notification.Category.INSTITUTION
            ).exists()
        )
        self.assertFalse(Notification.objects.filter(recipient=inactive_staff).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = make_user(email="viewer@example.com")
        self.other = make_user(email="other-viewer@example.com")
        self.notification = Notification.objects.create(
            recipient=self.user,
            title="Your own notification",
            message="Visible only to you.",
            url=reverse("notifications:list"),
        )
        self.other_notification = Notification.objects.create(
            recipient=self.other,
            title="Someone else's notification",
            message="Must not leak.",
        )

    def test_list_is_scoped_to_the_signed_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your own notification")
        self.assertNotContains(response, "Someone else&#x27;s notification")

    def test_mark_read_redirects_to_local_url(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("notifications:mark_read", args=[self.notification.pk]))
        self.assertRedirects(response, reverse("notifications:list"), fetch_redirect_response=False)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_another_users_notification_read(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("notifications:mark_read", args=[self.other_notification.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_mark_all_read_only_affects_the_current_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("notifications:mark_all_read"))
        self.assertRedirects(response, reverse("notifications:list"), fetch_redirect_response=False)
        self.notification.refresh_from_db()
        self.other_notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertFalse(self.other_notification.is_read)

    def test_preferences_page_requires_login(self):
        response = self.client.get(reverse("notifications:preferences"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_preferences_can_be_updated(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("notifications:preferences"),
            {
                "job_alerts": "on",
                "application_updates": "on",
                "institution_updates": "",
                "marketing": "on",
            },
        )
        self.assertRedirects(
            response, reverse("notifications:preferences"), fetch_redirect_response=False
        )
        preference = EmailPreference.objects.get(user=self.user)
        self.assertTrue(preference.marketing)
        self.assertFalse(preference.institution_updates)


class UnsubscribeTests(TestCase):
    def setUp(self):
        self.user = make_user(email="unsubscribe@example.com")
        self.preference = EmailPreference.objects.create(user=self.user, marketing=True)
        self.token = signing.dumps({"user_id": str(self.user.pk)}, salt="email-preferences")

    def test_valid_link_shows_confirmation_page(self):
        response = self.client.get(reverse("notifications:unsubscribe", args=[self.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "unsubscribe")

    def test_post_disables_marketing_email(self):
        response = self.client.post(reverse("notifications:unsubscribe", args=[self.token]))
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.preference.refresh_from_db()
        self.assertFalse(self.preference.marketing)

    def test_invalid_token_returns_404(self):
        response = self.client.get(reverse("notifications:unsubscribe", args=["not-a-token"]))
        self.assertEqual(response.status_code, 404)
