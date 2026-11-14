from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince

from apps.core.utils import initials

register = template.Library()


@register.filter
def salary_short(value):
    """Compact Indian salary formatting for vacancy cards and detail pages."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    if amount >= 10000000:
        return mark_safe(f"₹{escape(f'{amount / 10000000:.1f}')} Cr")
    if amount >= 100000:
        return mark_safe(f"₹{escape(f'{amount / 100000:.1f}')} L")
    if amount >= 1000:
        return mark_safe(f"₹{escape(f'{amount / 1000:.0f}')}K")
    return mark_safe(f"₹{escape(f'{amount:.0f}')}")


@register.filter
def user_initials(user):
    return initials(getattr(user, "full_name", "") or getattr(user, "email", ""))


@register.filter
def time_ago(value):
    if not value:
        return ""
    return f"{timesince(value)} ago"


@register.simple_tag(takes_context=True)
def query_url(context, **kwargs):
    """Builds a URL preserving current query params, replacing given keys."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    if "page" not in kwargs:
        params.pop("page", None)
    encoded = params.urlencode()
    base = request.path if request else ""
    return f"{base}?{encoded}" if encoded else base


@register.simple_tag
def absolute_url(path):
    return f"{settings.SITE_URL}{path}"


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
