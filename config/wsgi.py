import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_wsgi_application()

logger = logging.getLogger(__name__)

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
        logger.exception("Reference-data seeding failed")


# Optional one-time bootstrap for the first Django admin account on hosts
# where an interactive shell is unavailable (for example, Render Free).
# Set both variables in the host's Environment settings. Existing accounts
# are never modified and their passwords are never reset by this code.
admin_email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
admin_password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")

if admin_email and admin_password:
    try:
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password

        User = get_user_model()
        if not User.objects.filter(email__iexact=admin_email).exists():
            admin_name = os.environ.get(
                "DJANGO_SUPERUSER_FULL_NAME",
                "Platform Administrator",
            ).strip() or "Platform Administrator"
            validate_password(admin_password)
            User.objects.create_superuser(
                email=admin_email,
                password=admin_password,
                full_name=admin_name,
            )
            logger.warning(
                "Initial Django superuser created for configured admin email."
            )
        else:
            logger.info(
                "Configured Django superuser email already exists; no account changes made."
            )
    except Exception:
        # Keep the public site available; inspect Render logs if bootstrap fails.
        logger.exception("Initial Django superuser bootstrap failed")
elif admin_email or admin_password:
    logger.error(
        "Set both DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD "
        "to enable initial admin bootstrap."
    )
