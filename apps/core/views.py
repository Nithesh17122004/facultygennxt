"""Public information pages, contact, newsletter and SEO endpoints."""
import json
from datetime import timedelta
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.audit.services import log_action
from apps.institutions.models import Institution
from apps.jobs.models import Department, Job
from apps.jobs.services import homepage_data
from apps.notifications.services import notify_staff, send_email

from .forms import ContactForm, NewsletterForm
from .models import BlogPost, ContactEnquiry, FAQ, NewsletterSubscriber

COOKIE_NAME = "fng_cookie_preferences"


def _canonical(path=""):
    return f"{settings.SITE_URL}{path}"


def home(request):
    context = homepage_data()
    context.update(
        {
            "page_title": "FacultyNxtGen — Verified faculty and academic jobs in India",
            "meta_description": (
                "Explore verified teaching, research and non-teaching vacancies at Indian "
                "universities and colleges. Review eligibility, official notifications and deadlines."
            ),
            "canonical_url": _canonical(reverse("core:home")),
            "departments": Department.objects.filter(is_active=True, jobs__status="published", jobs__is_deleted=False)
            .annotate(
                live_count=Count(
                    "jobs",
                    filter=Q(jobs__status="published", jobs__is_deleted=False),
                    distinct=True,
                )
            )
            .filter(live_count__gt=0)
            .order_by("-live_count", "name")[:8],
            "hiring_institutions": Institution.objects.filter(
                verification_status="verified", is_active=True
            )
            .annotate(
                live_jobs_count=Count(
                    "jobs",
                    filter=Q(jobs__status="published", jobs__is_deleted=False),
                    distinct=True,
                )
            )
            .filter(live_jobs_count__gt=0)
            .order_by("-live_jobs_count", "name")[:4],
            "faqs": FAQ.objects.filter(is_published=True)[:5],
            "newsletter_form": NewsletterForm(),
        }
    )
    return render(request, "public/home.html", context)


def about(request):
    return render(
        request,
        "public/about.html",
        {
            "page_title": "About FacultyNxtGen",
            "meta_description": "Why FacultyNxtGen exists, how verification works, and the standards we hold institutions and vacancies to.",
            "canonical_url": _canonical(reverse("core:about")),
        },
    )


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        enquiry = form.save(commit=False)
        enquiry.consent = True
        enquiry.save()
        log_action(
            action="contact.enquiry_received",
            summary=f"Contact enquiry: {enquiry.subject}",
            entity_type="contact_enquiry",
            entity_id=enquiry.pk,
            request=request,
        )
        notify_staff(
            "New contact enquiry",
            f"{enquiry.name} ({enquiry.email}) — {enquiry.get_purpose_display()}: {enquiry.subject}",
            reverse("dashboard:content"),
        )
        send_email(
            recipient=enquiry.email,
            subject="We received your FacultyNxtGen enquiry",
            template="contact_received",
            category="transactional",
            context={
                "enquiry": enquiry,
                "reference": str(enquiry.reference)[:8].upper(),
            },
        )
        messages.success(
            request,
            f"Thank you. Your enquiry reference is {str(enquiry.reference)[:8].upper()}. "
            "Our team will respond within two working days.",
        )
        return redirect("core:contact")
    return render(
        request,
        "public/contact.html",
        {
            "form": form,
            "page_title": "Contact FacultyNxtGen",
            "meta_description": "Contact the FacultyNxtGen team for institution verification, free job posting, candidate support or privacy requests.",
            "canonical_url": _canonical(reverse("core:contact")),
        },
    )


def advertise(request):
    return render(
        request,
        "public/advertise.html",
        {
            "page_title": "Advertise academic vacancies — FacultyNxtGen",
            "meta_description": "Post academic vacancies free on FacultyNxtGen. Reach qualified faculty and researchers across India after institution verification.",
            "canonical_url": _canonical(reverse("core:advertise")),
        },
    )


def faq(request):
    faqs = FAQ.objects.filter(is_published=True)
    categories = {}
    for item in faqs:
        categories.setdefault(item.category, []).append(item)
    return render(
        request,
        "public/faq.html",
        {
            "faq_categories": categories,
            "page_title": "Frequently asked questions — FacultyNxtGen",
            "meta_description": "Answers about candidate accounts, institution verification, free job posting, job approval, applications and privacy.",
            "canonical_url": _canonical(reverse("core:faq")),
        },
    )


def blog_list(request):
    posts = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED, published_at__lte=timezone.now()
    ).select_related("author")
    category = (request.GET.get("category") or "").strip()[:80]
    if category:
        posts = posts.filter(category=category)
    paginator = Paginator(posts, 9)
    page = paginator.get_page(request.GET.get("page"))
    categories = (
        BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED, published_at__lte=timezone.now()
        )
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    return render(
        request,
        "public/blog_list.html",
        {
            "page_obj": page,
            "category": category,
            "categories": categories,
            "page_title": "Academic career resources — FacultyNxtGen",
            "meta_description": "Practical guidance on academic applications, interviews, eligibility and career decisions in Indian higher education.",
            "canonical_url": _canonical(reverse("core:blog")),
        },
    )


def blog_detail(request, slug):
    post = get_object_or_404(
        BlogPost.objects.select_related("author"),
        slug=slug,
        status=BlogPost.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    )
    related = (
        BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED,
            published_at__lte=timezone.now(),
            category=post.category,
        )
        .exclude(pk=post.pk)[:3]
    )
    return render(
        request,
        "public/blog_detail.html",
        {
            "post": post,
            "related_posts": related,
            "page_title": post.seo_title or post.title,
            "meta_description": post.seo_description or post.excerpt,
            "canonical_url": _canonical(post.get_absolute_url()),
            "og_type": "article",
            "og_image": post.cover_image.url if post.cover_image else "",
        },
    )


def privacy(request):
    return render(
        request,
        "public/privacy.html",
        {
            "page_title": "Privacy policy — FacultyNxtGen",
            "meta_description": "How FacultyNxtGen collects, uses, stores and deletes personal data, and how to exercise your privacy rights.",
            "canonical_url": _canonical(reverse("core:privacy")),
            "retention_days": settings.CANDIDATE_DATA_RETENTION_DAYS,
        },
    )


def terms(request):
    return render(
        request,
        "public/terms.html",
        {
            "page_title": "Terms of use — FacultyNxtGen",
            "meta_description": "The terms that govern candidate and institution use of FacultyNxtGen.",
            "canonical_url": _canonical(reverse("core:terms")),
        },
    )


def disclaimer(request):
    return render(
        request,
        "public/disclaimer.html",
        {
            "page_title": "Disclaimer — FacultyNxtGen",
            "meta_description": "Important information about vacancy verification, third-party application links and recruitment decisions.",
            "canonical_url": _canonical(reverse("core:disclaimer")),
        },
    )


def cookies(request):
    current = {}
    raw = request.COOKIES.get(COOKIE_NAME, "")
    if raw:
        try:
            current = json.loads(raw)
        except ValueError:
            current = {}
    if request.method == "POST":
        preferences = {
            "essential": True,
            "analytics": request.POST.get("analytics") == "on",
            "marketing": request.POST.get("marketing") == "on",
            "saved_at": timezone.now().isoformat(),
        }
        response = redirect("core:cookies")
        response.set_cookie(
            COOKIE_NAME,
            json.dumps(preferences, separators=(",", ":")),
            max_age=60 * 60 * 24 * 180,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )
        messages.success(request, "Your cookie preferences have been saved.")
        return response
    return render(
        request,
        "public/cookies.html",
        {
            "preferences": current,
            "page_title": "Cookie preferences — FacultyNxtGen",
            "meta_description": "Control optional analytics and marketing cookies on FacultyNxtGen.",
            "canonical_url": _canonical(reverse("core:cookies")),
        },
    )


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def newsletter_subscribe(request):
    if request.method != "POST":
        return redirect("core:home")
    form = NewsletterForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid email address and confirm consent to subscribe.")
        return redirect(request.POST.get("next") or "core:home")
    email = form.cleaned_data["email"]
    subscriber, _ = NewsletterSubscriber.objects.get_or_create(email=email)
    if subscriber.is_active:
        messages.info(request, "This email is already subscribed.")
        return redirect("core:home")
    subscriber.name = form.cleaned_data.get("name", "")[:120]
    subscriber.source = "website"
    subscriber.consent_text = "Website newsletter form; double opt-in confirmation required."
    from apps.core.utils import get_client_ip

    subscriber.consent_ip = get_client_ip(request)
    subscriber.save()
    confirmation_url = (
        f"{settings.SITE_URL}{reverse('core:newsletter_confirm', args=[subscriber.confirmation_token])}"
    )
    send_email(
        recipient=email,
        subject="Confirm your FacultyNxtGen newsletter subscription",
        template="newsletter_confirm",
        category="marketing",
        context={
            "subscriber": subscriber,
            "confirmation_url": confirmation_url,
            "unsubscribe_url": subscriber.get_unsubscribe_url(),
        },
    )
    messages.success(request, "Almost done. Check your inbox and confirm your subscription.")
    return redirect("core:home")


@ratelimit(key="ip", rate="20/m", method="GET", block=True)
def newsletter_confirm(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if not subscriber.is_active:
        subscriber.confirm()
    return render(request, "public/newsletter_confirmed.html", {"subscriber": subscriber})


@ratelimit(key="ip", rate="20/m", method="GET", block=True)
def newsletter_unsubscribe(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, unsubscribe_token=token)
    if subscriber.is_active:
        subscriber.unsubscribe()
    return render(request, "public/newsletter_unsubscribed.html", {"subscriber": subscriber})


def sitemap_xml(request):
    entries = []
    now = timezone.now()

    def add(path, lastmod=None, changefreq="weekly", priority="0.6"):
        entries.append(
            {
                "loc": f"{settings.SITE_URL}{path}",
                "lastmod": (lastmod or now).date().isoformat(),
                "changefreq": changefreq,
                "priority": priority,
            }
        )

    for name, priority in [
        ("core:home", "1.0"),
        ("jobs:find", "0.9"),
        ("jobs:teaching", "0.8"),
        ("jobs:research", "0.8"),
        ("jobs:non_teaching", "0.8"),
        ("core:about", "0.5"),
        ("core:advertise", "0.7"),
        ("institutions:directory", "0.7"),
        ("core:faq", "0.5"),
        ("core:blog", "0.6"),
        ("core:contact", "0.4"),
        ("core:privacy", "0.3"),
        ("core:terms", "0.3"),
        ("core:disclaimer", "0.3"),
    ]:
        add(reverse(name), now, "weekly", priority)

    for job in Job.objects.live().only("slug", "updated_at")[:5000]:
        add(job.get_absolute_url(), job.updated_at, "daily", "0.8")
    for institution in Institution.objects.filter(
        verification_status="verified", is_active=True
    ).only("slug", "updated_at")[:2000]:
        add(institution.get_absolute_url(), institution.updated_at, "weekly", "0.6")
    for post in BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED, published_at__lte=now
    ).only("slug", "updated_at")[:1000]:
        add(post.get_absolute_url(), post.updated_at, "monthly", "0.5")

    body = "\n".join(
        "<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
        "<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>".format(
            loc=escape(item["loc"]),
            lastmod=item["lastmod"],
            changefreq=item["changefreq"],
            priority=item["priority"],
        )
        for item in entries
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{body}</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /dashboard/",
        "Disallow: /applications/",
        "Disallow: /documents/",
        "Disallow: /notifications/",
        "Disallow: /search/",
        f"Sitemap: {settings.SITE_URL}{reverse('core:sitemap')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def ratelimited(request, exception=None):
    response = render(request, "errors/429.html", status=429)
    response["Retry-After"] = "60"
    return response


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_400(request, exception=None):
    return render(request, "errors/400.html", status=400)
