from django import template

from apps.documents.services import build_download_url

register = template.Library()


@register.simple_tag
def document_url(document, user):
    if not document:
        return ""
    return build_download_url(document, user)
