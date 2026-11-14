"""Remove the retired payment, subscription and paid-placement schema.

FacultyNxtGen launched as a free platform. These tables belonged to the
withdrawn Razorpay/subscription design and are no longer referenced by any
active model, view, form, task or template. Candidate, institution, job and
application records are untouched.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="Advertisement"),
        migrations.DeleteModel(name="InstitutionSubscription"),
        migrations.DeleteModel(name="Refund"),
        migrations.DeleteModel(name="Payment"),
        migrations.DeleteModel(name="Invoice"),
        migrations.DeleteModel(name="Order"),
        migrations.DeleteModel(name="WebhookEvent"),
        migrations.DeleteModel(name="Plan"),
    ]
