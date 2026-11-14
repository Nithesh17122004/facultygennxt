"""Reclassify notifications created by the retired payment workflow.

Existing rows may still use the removed ``payment`` category. They are moved to
the account category so notification rendering and filters remain valid. This is
a data-only migration; no candidate, institution, job or application data is
removed.
"""
from django.db import migrations


def reclassify_payment_notifications(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.filter(category="payment").update(category="account")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_alter_notification_category"),
    ]

    operations = [
        migrations.RunPython(reclassify_payment_notifications, noop),
    ]
