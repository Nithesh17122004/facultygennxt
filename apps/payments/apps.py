"""Migration-only app retained to remove the retired payment tables.

FacultyNxtGen is free for candidates and educational institutions. This app no
longer contains models, views, URLs, admin registrations, tasks or services, so
it cannot execute any payment workflow. It remains installed solely so that
existing databases can apply ``0002_remove_payment_models`` and drop the legacy
payment tables during ``manage.py migrate``.
"""
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments (retired)"
