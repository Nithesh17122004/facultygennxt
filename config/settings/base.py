"""Shared settings for every FacultyNxtGen environment."""
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import BASE_DIR, database_config, env, env_bool, env_int, env_list

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-development-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

SITE_NAME = "FacultyNxtGen"
SITE_TAGLINE = "The Next Generation of Academic Careers."
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000").rstrip("/")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "support@facultynxtgen.com")
CONTACT_PHONE = env("CONTACT_PHONE", "+91 90000 00000")
CONTACT_ADDRESS = env(
    "CONTACT_ADDRESS", "FacultyNxtGen, Bengaluru, Karnataka, India"
)
SOCIAL_LINKEDIN = env("SOCIAL_LINKEDIN", "")
SOCIAL_INSTAGRAM = env("SOCIAL_INSTAGRAM", "")
SOCIAL_X = env("SOCIAL_X", "")

DEMO_MODE = env_bool("DEMO_MODE", False)

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_ratelimit",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.documents",
    "apps.candidates",
    "apps.institutions",
    "apps.jobs",
    "apps.applications",
    # Migration-only: drops the retired payment tables, exposes no runtime code.
    "apps.payments",
    "apps.notifications",
    "apps.audit",
    "apps.dashboard",
    "apps.search",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    # MessageMiddleware must run before custom middleware that calls messages.*.
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.accounts.middleware.StaffMFAEnforcementMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.LastSeenMiddleware",
    "django_ratelimit.middleware.RatelimitMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Development may run on SQLite; production.py requires PostgreSQL explicitly.
DATABASES = {"default": database_config(default_sqlite=True)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailAuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard_redirect"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

SESSION_COOKIE_NAME = "fng_session"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 8)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # allows fetch() calls to read the CSRF token
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# URLs, i18n, time
# ---------------------------------------------------------------------------
APPEND_SLASH = True
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media" / "public"
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "media" / "private")))
PRIVATE_MEDIA_URL = "/documents/"  # never served directly; routed through access checks

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
    "private": {
        "BACKEND": "apps.documents.storage.PrivateDocumentStorage",
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640
MAX_DOCUMENT_SIZE = env_int("MAX_DOCUMENT_SIZE", 5 * 1024 * 1024)
MAX_IMAGE_SIZE = env_int("MAX_IMAGE_SIZE", 2 * 1024 * 1024)
CLAMAV_HOST = env("CLAMAV_HOST", "")
CLAMAV_PORT = env_int("CLAMAV_PORT", 3310)

# ---------------------------------------------------------------------------
# Cache, email, background work
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "facultynxtgen-default",
    }
}
RATELIMIT_VIEW = "apps.core.views.ratelimited"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", f"FacultyNxtGen <noreply@facultynxtgen.com>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
RESEND_API_KEY = env("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = env("RESEND_FROM_EMAIL", DEFAULT_FROM_EMAIL)
RESEND_WEBHOOK_SECRET = env("RESEND_WEBHOOK_SECRET", "")
EMAIL_VERIFICATION_MAX_AGE = env_int("EMAIL_VERIFICATION_MAX_AGE", 60 * 60 * 48)

REDIS_URL = env("REDIS_URL", "")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL or "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL or "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "expire-jobs-hourly": {
        "task": "apps.jobs.tasks.expire_jobs",
        "schedule": 3600.0,
    },
    "send-job-alerts-daily": {
        "task": "apps.jobs.tasks.send_job_alerts",
        "schedule": 86400.0,
    },
}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# Security / privacy
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:")
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)

MFA_REQUIRED_FOR_STAFF = env_bool("MFA_REQUIRED_FOR_STAFF", not DEBUG)
MFA_ISSUER = env("MFA_ISSUER", "FacultyNxtGen")
LOGIN_MAX_FAILED_ATTEMPTS = env_int("LOGIN_MAX_FAILED_ATTEMPTS", 5)
LOGIN_LOCKOUT_MINUTES = env_int("LOGIN_LOCKOUT_MINUTES", 15)

# ---------------------------------------------------------------------------
# Third-party observability
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", "development")

# ---------------------------------------------------------------------------
# Uploads and verification
# ---------------------------------------------------------------------------
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DOCUMENT_DOWNLOAD_LINK_TTL = env_int("DOCUMENT_DOWNLOAD_LINK_TTL", 600)
INSTITUTION_VERIFICATION_WINDOW_DAYS = 7
JOB_REVIEW_WINDOW_DAYS = 3
CANDIDATE_DATA_RETENTION_DAYS = env_int("CANDIDATE_DATA_RETENTION_DAYS", 365)
AUDIT_LOG_RETENTION_DAYS = env_int("AUDIT_LOG_RETENTION_DAYS", 730)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "facultynxtgen.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "facultynxtgen": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "facultynxtgen.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

if not SECRET_KEY or len(SECRET_KEY) < 30:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a long random value.")
