import logging

from celery import shared_task

logger = logging.getLogger("facultynxtgen.email")


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_email_task(self, log_id, reply_to=None):
    from .services import _dispatch

    _dispatch(log_id, reply_to=reply_to)
    from .models import EmailLog

    try:
        log = EmailLog.objects.get(pk=log_id)
    except EmailLog.DoesNotExist:
        return
    if log.status == EmailLog.Status.FAILED and log.attempts < 3:
        raise self.retry(exc=RuntimeError(log.error or "Email delivery failed"))
