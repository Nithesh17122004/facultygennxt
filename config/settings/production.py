
"""Production settings. Every secret is supplied by the environment."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403,F401
from .env import database_config, env, env_bool, env_int, env_list

DEBUG = False

# Security: Django secret key
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or len(SECRET_KEY) < 40:
    raise ImproperlyConfigured(
        "Set a strong DJANGO_SECRET_KEY (40+ characters)."
    )

# Allowed hosts and CSRF
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", [])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be configured in production."
    )

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "CSRF_TRUSTED_ORIGINS must be configured in production."
    )

# PostgreSQL database
DATABASES = {"default": database_config(default_sqlite=False)}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    raise ImproperlyConfigured(
        "PostgreSQL is required in production."
    )

# Redis cache
REDIS_URL = env("REDIS_URL", "redis://127.0.0.1:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient"
        },
        "TIMEOUT": 300,
    }
}

# File storage
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
    "private": {
        "BACKEND": "apps.documents.storage.PrivateDocumentStorage"
    },
}

# Security settings
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
# Render terminates HTTPS at its edge and forwards the original scheme.
# Trust X-Forwarded-Proto so Django recognizes external HTTPS requests.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", True
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
CSRF_COOKIE_HTTPONLY = False

# Admin MFA
MFA_REQUIRED_FOR_STAFF = env_bool(
    "MFA_REQUIRED_FOR_STAFF", True
)

# =====================================================
# EMAIL CONFIGURATION - RESEND
# =====================================================

# Resend API key (also available to the notification service)
RESEND_API_KEY = env("RESEND_API_KEY", "")

# Django SMTP email backend
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = env("EMAIL_HOST", "smtp.resend.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587)

EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = False

EMAIL_HOST_USER = env("EMAIL_HOST_USER", "resend")

# Use Resend API key as SMTP password unless separately configured
EMAIL_HOST_PASSWORD = env(
    "EMAIL_HOST_PASSWORD",
    RESEND_API_KEY
)

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    "FacultyGenNxt <onboarding@resend.dev>"
)

# =====================================================
# CELERY CONFIGURATION - REDIS
# =====================================================

CELERY_TASK_ALWAYS_EAGER = False

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    REDIS_URL
)

CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    REDIS_URL
)

# =====================================================
# LOGGING
# =====================================================

LOGGING["root"]["handlers"] = ["console"]  # noqa: F405
LOGGING["loggers"]["django.request"]["handlers"] = [
    "console"
]  # noqa: F405
LOGGING["loggers"]["facultynxtgen"]["handlers"] = [
    "console"
]  # noqa: F405
LOGGING["loggers"]["facultynxtgen.security"]["handlers"] = [
    "console"
]  # noqa: F405

# =====================================================
# SENTRY ERROR MONITORING
# =====================================================

if SENTRY_DSN:  # noqa: F405
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,  # noqa: F405
        integrations=[DjangoIntegration()],
        environment=SENTRY_ENVIRONMENT,  # noqa: F405
        traces_sample_rate=float(
            env("SENTRY_TRACES_SAMPLE_RATE", "0.1")
        ),
        send_default_pii=False,
    )
