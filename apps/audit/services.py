import logging

from .models import AuditLog

logger = logging.getLogger("facultynxtgen.security")


def log_action(
    *,
    action,
    summary,
    actor=None,
    entity_type="",
    entity_id="",
    metadata=None,
    request=None,
):
    """Records an audit event without ever blocking the underlying action."""
    ip_address = None
    user_agent = ""
    if request is not None:
        from apps.core.utils import get_client_ip

        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:400]
        if actor is None and request.user.is_authenticated:
            actor = request.user
    try:
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ""),
            summary=summary[:500],
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:  # pragma: no cover - audit must never break user flow
        logger.exception("Could not write audit log: %s", action)
        return None
