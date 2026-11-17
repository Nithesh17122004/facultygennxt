from django.conf import settings


def site_context(request):
    """Small, cache-friendly values required by every rendered page."""
    unread_notifications = 0
    dashboard_url = None
    # Error handlers can run before AuthenticationMiddleware has attached
    # request.user (for example, when CommonMiddleware rejects an invalid host).
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from apps.notifications.models import Notification

        unread_notifications = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
        dashboard_url = user.get_dashboard_url()

    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_URL": settings.SITE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "CONTACT_PHONE": settings.CONTACT_PHONE,
        "CONTACT_ADDRESS": settings.CONTACT_ADDRESS,
        "SOCIAL_LINKEDIN": settings.SOCIAL_LINKEDIN,
        "SOCIAL_INSTAGRAM": settings.SOCIAL_INSTAGRAM,
        "SOCIAL_X": settings.SOCIAL_X,
        "DEMO_MODE": settings.DEMO_MODE,
        "unread_notifications": unread_notifications,
        "dashboard_url": dashboard_url,
        "csp_nonce": getattr(request, "csp_nonce", ""),
        "current_year": __import__("datetime").date.today().year,
    }
