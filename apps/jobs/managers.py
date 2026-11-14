from django.db import models
from django.utils import timezone


class JobQuerySet(models.QuerySet):
    def live(self):
        return self.filter(
            status="published",
            is_deleted=False,
            deadline__gte=timezone.localdate(),
            institution__verification_status="verified",
            institution__is_active=True,
        )

    def for_institution(self, institution):
        return self.filter(institution=institution, is_deleted=False)

