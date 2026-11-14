"""Transactional email delivery through Resend with a safe Django fallback."""
import logging
import re
from html import unescape as html_unescape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from apps.audit.services import log_action
from .models import EmailLog, EmailPreference, Notification

logger = logging.getLogger("facultynxtgen.email")


def _unsubscribe_url(user):
    from django.core import signing

    token = signing.dumps({"user_id": str(user.pk)}, salt="email-preferences")
    return f"{settings.SITE_URL}{reverse('notifications:unsubscribe', args=[token])}"


def build_email_context(user, category, extra=None):
    from django.templatetags.static import static

    context = {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_URL": settings.SITE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "logo_url": f"{settings.SITE_URL}{static('images/facultynxtgen-logo.png')}",
        "user": user,
        "category": category,
        "current_year": timezone.localdate().year,
        "preferences_url": f"{settings.SITE_URL}{reverse('notifications:preferences')}",
    }
    if category == "marketing" and user is not None:
        context["unsubscribe_url"] = _unsubscribe_url(user)
    context.update(extra or {})
    return context


def send_email(
    *,
    recipient,
    subject,
    template,
    category="transactional",
    user=None,
    context=None,
    reply_to=None,
):
    """Renders and queues one email, logging every attempt.

    The rendered bodies are persisted on the log so async workers never need
    to reconstruct request-scoped objects such as jobs or applications.
    """
    recipient = (recipient or "").strip().lower()
    if not recipient:
        return None
    if user is not None:
        prefs, _ = EmailPreference.objects.get_or_create(user=user)
        if not prefs.allows(category):
            return EmailLog.objects.create(
                recipient_email=recipient,
                user=user,
                subject=subject,
                template=template,
                category=category,
                status=EmailLog.Status.SUPPRESSED,
            )

    email_context = build_email_context(user, category, context)
    log = EmailLog.objects.create(
        recipient_email=recipient,
        user=user,
        subject=subject,
        template=template,
        category=category,
        status=EmailLog.Status.QUEUED,
    )
    if not _render_email(log, email_context):
        return log

    if settings.CELERY_TASK_ALWAYS_EAGER or settings.DEBUG:
        _dispatch(log.pk, reply_to=reply_to)
    else:
        from .tasks import send_email_task

        transaction.on_commit(
            lambda: _safe_queue(send_email_task, log.pk, reply_to=reply_to)
        )
    return log


def _render_email(log, context):
    """Renders HTML and text bodies once, before the email is queued."""
    try:
        html_body = render_to_string(f"emails/{log.template}.html", context)
    except TemplateDoesNotExist:
        logger.exception("Missing email template %s", log.template)
        log.status = EmailLog.Status.FAILED
        log.error = "Email template missing."
        log.save(update_fields=["status", "error"])
        return False
    except Exception as exc:  # rendering must never break the request
        logger.exception("Email template rendering failed for %s", log.template)
        log.status = EmailLog.Status.FAILED
        log.error = f"Template render failed: {exc}"[:2000]
        log.save(update_fields=["status", "error"])
        return False
    try:
        text_body = render_to_string(f"emails/{log.template}.txt", context).strip()
    except TemplateDoesNotExist:
        text_body = html_unescape(strip_tags(html_body))
        text_body = re.sub(r"[ \t]+", " ", text_body)
        text_body = re.sub(r"\n{3,}", "\n\n", text_body).strip()
    except Exception:
        logger.exception("Email text rendering failed for %s", log.template)
        text_body = html_unescape(strip_tags(html_body))
        text_body = re.sub(r"\n{3,}", "\n\n", text_body).strip()
    log.rendered_html = html_body
    log.rendered_text = text_body
    log.save(update_fields=["rendered_html", "rendered_text"])
    return True


def _safe_queue(task, log_id, **kwargs):
    try:
        task.delay(log_id, **kwargs)
    except Exception:  # pragma: no cover - broker outage fallback
        logger.exception("Celery unavailable; sending email synchronously.")
        _dispatch(log_id, **kwargs)


def _dispatch(log_id, reply_to=None):
    try:
        log = EmailLog.objects.get(pk=log_id)
    except EmailLog.DoesNotExist:
        return
    if log.status == EmailLog.Status.SENT:
        return

    html_body = log.rendered_html
    text_body = log.rendered_text
    if not html_body:
        # Compatibility fallback for logs created before bodies were stored.
        context = build_email_context(log.user, log.category)
        try:
            html_body = render_to_string(f"emails/{log.template}.html", context)
        except TemplateDoesNotExist:
            logger.exception("Missing email template %s", log.template)
            log.status = EmailLog.Status.FAILED
            log.error = "Email template missing."
            log.save(update_fields=["status", "error"])
            return
        try:
            text_body = render_to_string(f"emails/{log.template}.txt", context).strip()
        except TemplateDoesNotExist:
            text_body = html_unescape(strip_tags(html_body))
            text_body = re.sub(r"\n{3,}", "\n\n", text_body).strip()

    log.attempts += 1
    try:
        provider_id = ""
        provider = "django"
        if settings.RESEND_API_KEY:
            provider_id = _send_with_resend(
                recipient=log.recipient_email,
                subject=log.subject,
                html=html_body,
                text=text_body,
                reply_to=reply_to,
            )
            provider = "resend"
        else:
            message = EmailMultiAlternatives(
                subject=log.subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[log.recipient_email],
                reply_to=reply_to or [settings.SUPPORT_EMAIL],
            )
            message.attach_alternative(html_body, "text/html")
            message.send(fail_silently=False)
            provider = "django"
        log.status = EmailLog.Status.SENT
        log.provider = provider
        log.provider_message_id = provider_id or ""
        log.sent_at = timezone.now()
        log.error = ""
        log.save(update_fields=["status", "provider", "provider_message_id", "sent_at", "error", "attempts"])
    except Exception as exc:
        logger.exception("Email delivery failed for log %s", log.pk)
        log.status = EmailLog.Status.FAILED
        log.error = str(exc)[:2000]
        log.save(update_fields=["status", "error", "attempts"])


def _send_with_resend(*, recipient, subject, html, text, reply_to=None):
    import requests

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [recipient],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    response = requests.post(
        "https://api.resend.com/emails",
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=12,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend error {response.status_code}: {response.text[:500]}")
    return response.json().get("id", "")


def notify_user(
    user,
    *,
    title,
    message,
    url="",
    category=Notification.Category.ACCOUNT,
    level=Notification.Level.INFO,
):
    if user is None:
        return None
    return Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        url=url,
        category=category,
        level=level,
    )


def notify_staff(title, message, url=""):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    staff = User.objects.filter(is_active=True, is_staff=True)
    bulk = [
        Notification(
            recipient=member,
            title=title,
            message=message,
            url=url,
            category=Notification.Category.INSTITUTION,
            level=Notification.Level.WARNING,
        )
        for member in staff
    ]
    return Notification.objects.bulk_create(bulk)
