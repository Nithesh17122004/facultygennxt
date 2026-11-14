from django.core.management.base import BaseCommand

from apps.jobs.services import send_due_job_alerts


class Command(BaseCommand):
    help = "Send due job alert digest emails."

    def handle(self, *args, **options):
        sent = send_due_job_alerts()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} job alert digest(s)."))
