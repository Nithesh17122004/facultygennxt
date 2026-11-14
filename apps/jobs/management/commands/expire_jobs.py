from django.core.management.base import BaseCommand

from apps.jobs.models import Job
from apps.jobs.services import expire_due_jobs


class Command(BaseCommand):
    help = "Mark published jobs past their application deadline as expired."

    def handle(self, *args, **options):
        count = expire_due_jobs()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} job(s)."))
