import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_wsgi_application()

# Keep the small reference tables available on Render's Free plan, where
# a separate pre-deploy command / shell is not available. The seed command is
# idempotent and does not modify user accounts, vacancies or applications.
if os.environ.get("FNG_SEED_REFERENCE_ON_START", "true").lower() in {"1", "true", "yes"}:
    from django.core.management import call_command

    try:
        call_command("seed_reference", verbosity=0)
    except Exception:
        # Do not take the public site offline if reference-data seeding has a
        # transient database issue. The error will be visible in Render logs.
        import logging

        logging.getLogger(__name__).exception("Reference-data seeding failed")
