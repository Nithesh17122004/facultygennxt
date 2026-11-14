from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User

from .models import CandidateProfile


@receiver(post_save, sender=User)
def ensure_candidate_profile(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created and instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
