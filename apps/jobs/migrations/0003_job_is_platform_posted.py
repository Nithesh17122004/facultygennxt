from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_alter_job_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="is_platform_posted",
            field=models.BooleanField(default=False),
        ),
    ]
