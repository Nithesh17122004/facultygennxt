import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.audit.services import log_action

from .models import Document
from .services import load_download_token, user_can_access_document

logger = logging.getLogger("facultynxtgen.documents")


@login_required
def download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    token = request.GET.get("token", "")
    try:
        payload = load_download_token(token)
    except Exception:
        raise Http404("This download link is invalid or has expired.")

    if payload.get("document_id") != str(document.pk) or payload.get("user_id") != str(request.user.pk):
        raise Http404("This download link is invalid.")
    if not user_can_access_document(request.user, document):
        return HttpResponseForbidden("You are not allowed to access this document.")
    try:
        handle = document.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("This file is no longer available.") from exc

    log_action(
        action="document.downloaded",
        summary=f"Downloaded document {document.pk}",
        actor=request.user,
        entity_type="document",
        entity_id=document.pk,
        request=request,
    )
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=document.original_name or f"{document.pk}.pdf",
        content_type=document.mime_type or "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk, owner=request.user, is_deleted=False)
    protected_purposes = {
        Document.Purpose.INSTITUTION_AUTHORIZATION,
        Document.Purpose.INSTITUTION_REGISTRATION,
        Document.Purpose.NOTIFICATION,
    }
    if document.purpose in protected_purposes:
        messages.error(
            request,
            "This document supports an institutional record or job notice and cannot be removed.",
        )
        return redirect(request.POST.get("next") or "candidates:documents")
    document.soft_delete()
    log_action(
        action="document.deleted",
        summary=f"Deleted own document {document.pk}",
        actor=request.user,
        entity_type="document",
        entity_id=document.pk,
        request=request,
    )
    messages.success(request, "The document has been deleted.")
    return redirect(request.POST.get("next") or "candidates:documents")
