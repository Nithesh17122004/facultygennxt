"""Local development settings."""
from .base import *  # noqa: F403,F401
from .env import database_config, env, env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver", "0.0.0.0"]
INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
MFA_REQUIRED_FOR_STAFF = env_bool("MFA_REQUIRED_FOR_STAFF", False)

# Developers can opt into a Postgres URL; otherwise base's SQLite fallback is used.
DATABASES = {"default": database_config(default_sqlite=True)}

STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

# Console output stays readable during development.
LOGGING["root"]["level"] = "INFO"  # noqa: F405

# django-ratelimit requires a shared cache in production (Redis). LocMem is
# acceptable for a single-process development server.
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]
