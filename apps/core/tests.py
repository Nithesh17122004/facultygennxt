import json
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import BlogPost, ContactEnquiry, FAQ, NewsletterSubscriber
from apps.core.testing import make_institution, make_job, make_recruiter, make_user
from apps.jobs.models import Job
from apps.notifications.models import EmailLog, Notification


class PublicPageTests(TestCase):
    def test_public_information_pages_render(self):
        names = [
            "core:home",
            "core:about",
            "core:advertise",
            "core:faq",
            "core:contact",
            "core:privacy",
            "core:terms",
            "core:disclaimer",
            "core:cookies",
            "core:blog",
        ]
        for name in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "<html", html=False)

    def test_home_lists_only_live_vacancies(self):
        institution = make_institution()
        recruiter = make_recruiter(institution=institution)
        live_job = make_job(
            institution=institution,
            posted_by=recruiter,
            title="Live Assistant Professor Role",
            status=Job.Status.PUBLISHED,
        )
        draft_job = make_job(
            institution=institution,
            posted_by=recruiter,
            title="Draft Role That Must Stay Private",
            status=Job.Status.DRAFT,
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, live_job.title)
        self.assertNotContains(response, draft_job.title)

    def test_faq_page_groups_published_entries(self):
        FAQ.objects.create(question="How does verification work?", answer="We review documents.")
        FAQ.objects.create(
            question="Hidden question", answer="Not published.", is_published=False
        )
        response = self.client.get(reverse("core:faq"))
        self.assertContains(response, "How does verification work?")
        self.assertNotContains(response, "Hidden question")

    def test_unknown_url_uses_custom_404(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "errors/404.html")


class BlogTests(TestCase):
    def setUp(self):
        self.author = make_user(email="author@example.com")
        self.published = BlogPost.objects.create(
            title="How to prepare for an academic interview",
            excerpt="A practical guide for faculty candidates.",
            content="Prepare a teaching demonstration.\n\nKnow the institution.",
            author=self.author,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now() - timedelta(days=1),
        )
        self.draft = BlogPost.objects.create(
            title="Unpublished editorial draft",
            excerpt="Not ready.",
            content="Draft content.",
            author=self.author,
            status=BlogPost.Status.DRAFT,
        )

    def test_published_posts_appear_in_the_list(self):
        response = self.client.get(reverse("core:blog"))
        self.assertContains(response, self.published.title)
        self.assertNotContains(response, self.draft.title)

    def test_published_post_detail_renders(self):
        response = self.client.get(self.published.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.published.title)

    def test_draft_detail_is_not_public(self):
        response = self.client.get(self.draft.get_absolute_url())
        self.assertEqual(response.status_code, 404)


class ContactTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = make_user(email="staff@example.com")
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.payload = {
            "name": "Asha Rao",
            "email": "asha@example.com",
            "phone": "9876543210",
            "organization": "Example University",
            "purpose": ContactEnquiry.Purpose.INSTITUTION,
            "subject": "Institution verification question",
            "message": "Please explain the documents required for institution verification.",
            "consent": "on",
        }

    def test_valid_contact_enquiry_is_saved_and_acknowledged(self):
        response = self.client.post(reverse("core:contact"), self.payload)
        self.assertRedirects(response, reverse("core:contact"), fetch_redirect_response=False)
        enquiry = ContactEnquiry.objects.get(email="asha@example.com")
        self.assertTrue(enquiry.consent)
        self.assertEqual(enquiry.status, ContactEnquiry.Status.NEW)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff, title="New contact enquiry"
            ).exists()
        )
        log = EmailLog.objects.get(recipient_email="asha@example.com")
        self.assertEqual(log.template, "contact_received")
        self.assertEqual(log.status, EmailLog.Status.SENT)

    def test_short_message_is_rejected(self):
        payload = dict(self.payload, message="Too short")
        response = self.client.post(reverse("core:contact"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "message",
            "Please add enough detail for our team to help (at least 20 characters).",
        )
        self.assertFalse(ContactEnquiry.objects.exists())

    def test_consent_is_required(self):
        payload = dict(self.payload)
        payload.pop("consent")
        response = self.client.post(reverse("core:contact"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactEnquiry.objects.exists())

    def test_honeypot_submission_is_rejected(self):
        payload = dict(self.payload, website="https://spam.example.com")
        response = self.client.post(reverse("core:contact"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactEnquiry.objects.exists())


class NewsletterTests(TestCase):
    def setUp(self):
        cache.clear()

    def _subscribe(self, email="reader@example.com", **extra):
        payload = {"email": email, "name": "Reader", "consent": "on"}
        payload.update(extra)
        return self.client.post(reverse("core:newsletter_subscribe"), payload)

    def test_subscription_starts_inactive_and_sends_confirmation(self):
        response = self._subscribe()
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        subscriber = NewsletterSubscriber.objects.get(email="reader@example.com")
        self.assertFalse(subscriber.is_active)
        self.assertIsNotNone(subscriber.consent_ip)
        self.assertTrue(subscriber.consent_text)
        log = EmailLog.objects.get(recipient_email="reader@example.com")
        self.assertEqual(log.template, "newsletter_confirm")
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertIn(str(subscriber.confirmation_token), log.rendered_html)

    def test_confirmation_activates_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(email="confirm@example.com")
        response = self.client.get(
            reverse("core:newsletter_confirm", args=[subscriber.confirmation_token])
        )
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertIsNotNone(subscriber.confirmed_at)

    def test_unsubscribe_deactivates_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(
            email="leaving@example.com", is_active=True
        )
        response = self.client.get(
            reverse("core:newsletter_unsubscribe", args=[subscriber.unsubscribe_token])
        )
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)
        self.assertIsNotNone(subscriber.unsubscribed_at)

    def test_unknown_confirmation_token_returns_404(self):
        response = self.client.get(
            reverse(
                "core:newsletter_confirm",
                args=["00000000-0000-0000-0000-000000000000"],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_already_active_subscriber_does_not_get_another_email(self):
        NewsletterSubscriber.objects.create(
            email="active@example.com", is_active=True
        )
        response = self._subscribe(email="active@example.com")
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)
        self.assertFalse(
            EmailLog.objects.filter(recipient_email="active@example.com").exists()
        )


class CookiePreferenceTests(TestCase):
    def test_preferences_are_persisted_in_a_cookie(self):
        response = self.client.post(
            reverse("core:cookies"), {"analytics": "on", "marketing": ""}
        )
        self.assertRedirects(response, reverse("core:cookies"), fetch_redirect_response=False)
        cookie = response.cookies["fng_cookie_preferences"]
        preferences = json.loads(cookie.value)
        self.assertTrue(preferences["essential"])
        self.assertTrue(preferences["analytics"])
        self.assertFalse(preferences["marketing"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")


class SeoTests(TestCase):
    def setUp(self):
        self.institution = make_institution()
        self.recruiter = make_recruiter(institution=self.institution)
        self.job = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            status=Job.Status.PUBLISHED,
        )
        self.author = make_user(email="seo-author@example.com")
        self.post = BlogPost.objects.create(
            title="SEO test post",
            excerpt="Excerpt",
            content="Content",
            author=self.author,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_sitemap_includes_live_jobs_institutions_and_posts(self):
        response = self.client.get(reverse("core:sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        body = response.content.decode()
        self.assertIn(self.job.get_absolute_url(), body)
        self.assertIn(self.institution.get_absolute_url(), body)
        self.assertIn(self.post.get_absolute_url(), body)

    def test_sitemap_excludes_drafts(self):
        draft = make_job(
            institution=self.institution,
            posted_by=self.recruiter,
            title="Draft vacancy",
            status=Job.Status.DRAFT,
        )
        response = self.client.get(reverse("core:sitemap"))
        self.assertNotIn(draft.get_absolute_url(), response.content.decode())

    def test_robots_txt_points_to_the_sitemap(self):
        response = self.client.get(reverse("core:robots"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        body = response.content.decode()
        self.assertIn(f"Sitemap: ", body)
        self.assertIn(reverse("core:sitemap"), body)
        self.assertIn("Disallow: /dashboard/", body)
