import logging

from celery import shared_task

logger = logging.getLogger("facultynxtgen.jobs")


@shared_task
def expire_jobs():
    from .services import expire_due_jobs

    return expire_due_jobs()


@shared_task
def send_job_alerts():
    from .services import send_due_job_alerts

    return send_due_job_alerts()
