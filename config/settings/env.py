"""Environment helpers shared by all settings modules."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    value = os.getenv(key)
    return default if value is None or value == "" else value


def env_bool(key, default=False):
    value = os.getenv(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key, default=0):
    try:
        return int(env(key, default))
    except (TypeError, ValueError):
        return default


def env_list(key, default=None):
    raw = os.getenv(key)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def database_config(default_sqlite=True):
    """Build the database config from DATABASE_URL or POSTGRES_* variables.

    Production must provide PostgreSQL. Development keeps a SQLite fallback so
    contributors can run the app without a local server; no data model relies
    on SQLite-specific behaviour.
    """
    url = env("DATABASE_URL")
    if url:
        parsed = urlparse(url)
        engine = {
            "postgres": "django.db.backends.postgresql",
            "postgresql": "django.db.backends.postgresql",
            "sqlite": "django.db.backends.sqlite3",
        }.get(parsed.scheme)
        if not engine:
            raise ValueError("Unsupported DATABASE_URL scheme.")
        if parsed.scheme == "sqlite":
            return {"ENGINE": engine, "NAME": parsed.path.lstrip("/") or str(BASE_DIR / "db.sqlite3")}
        options = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        return {
            "ENGINE": engine,
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }

    if env("POSTGRES_DB"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"sslmode": env("POSTGRES_SSLMODE", "prefer")},
        }

    if not default_sqlite:
        raise RuntimeError("A PostgreSQL DATABASE_URL is required in production.")
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
