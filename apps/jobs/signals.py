from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Job, JobStatusHistory


@receiver(pre_save, sender=Job)
def capture_previous_status(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._previous_status = ""
        return
    instance._previous_status = (
        Job.objects.filter(pk=instance.pk).values_list("status", flat=True).first() or ""
    )


@receiver(post_save, sender=Job)
def record_job_status(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    previous = getattr(instance, "_previous_status", "")
    if not created and previous == instance.status:
        return
    JobStatusHistory.objects.create(
        job=instance,
        from_status=previous or "",
        to_status=instance.status,
        actor=getattr(instance, "_status_change_actor", None),
        note=getattr(instance, "_status_change_note", "") or ("Job record created" if created else ""),
    )
