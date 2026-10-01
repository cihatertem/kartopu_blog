"""Real PostgreSQL tests, never the SQLite search/migration shims.

Requires POSTGRES_TEST_HOST (127.0.0.1 or ::1), POSTGRES_TEST_PORT,
POSTGRES_TEST_DB (test_*), POSTGRES_TEST_USER and POSTGRES_TEST_PASSWORD.
Use a disposable local PostgreSQL 18 instance and a dedicated CREATEDB role
without production privileges. Django creates/drops POSTGRES_TEST_DB itself;
do not point these settings at a database containing anything worth keeping.
"""

import os
import re

from django.core.exceptions import ImproperlyConfigured


def _required_test_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        raise ImproperlyConfigured(
            f"{name} must be explicitly set for PostgreSQL tests."
        )
    return value


_test_host = _required_test_env("POSTGRES_TEST_HOST")
_test_port = _required_test_env("POSTGRES_TEST_PORT")
_test_db = _required_test_env("POSTGRES_TEST_DB")
_test_user = _required_test_env("POSTGRES_TEST_USER")
_test_password = _required_test_env("POSTGRES_TEST_PASSWORD")

if _test_host not in {"127.0.0.1", "::1"}:
    raise ImproperlyConfigured("POSTGRES_TEST_HOST must be a literal loopback address.")
if not _test_port.isdecimal() or not 1 <= int(_test_port) <= 65535:
    raise ImproperlyConfigured("POSTGRES_TEST_PORT must be an explicit valid TCP port.")
if not re.fullmatch(r"test_[a-z0-9_]+", _test_db) or len(_test_db) > 63:
    raise ImproperlyConfigured(
        "POSTGRES_TEST_DB must be a test_* identifier of at most 63 characters."
    )

from config.settings import *

SECRET_KEY = "postgresql-tests-only-not-for-deployment"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "[::1]"]
SECURE_SSL_REDIRECT = False
CSRF_TRUSTED_ORIGINS = []
TRUSTED_PROXY_NETS = []
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in {"silk", "storages"}]
MIDDLEWARE = [item for item in MIDDLEWARE if item != "silk.middleware.SilkyMiddleware"]

USE_PGBOUNCER = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _test_db,
        "USER": _test_user,
        "PASSWORD": _test_password,
        "HOST": _test_host,
        "PORT": _test_port,
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 5,
            # Pin the address too: inherited libpq PGHOSTADDR must not redirect us.
            "hostaddr": _test_host,
            "sslmode": "disable",
        },
        "TEST": {"NAME": _test_db, "MIGRATE": True},
    }
}
MIGRATION_MODULES = {}

CACHES = {
    alias: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"postgresql-tests-{alias}",
        "KEY_FUNCTION": SECURE_CACHE_KEY_FUNCTION,
    }
    for alias in CACHES
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

USE_S3 = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
# Empty roots prevent model cleanup signals from touching real uploads/output.
MEDIA_ROOT = ""
STATIC_ROOT = ""
MEDIA_URL = "/media/"
STATIC_URL = "/static/"
IMAGEKIT_DEFAULT_FILE_STORAGE = "django.core.files.storage.InMemoryStorage"
IMAGEKIT_CACHE_BACKEND = "default"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = "localhost"
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
DEFAULT_FROM_EMAIL = "tests@example.invalid"
SITE_BASE_URL = "http://testserver"
GOOGLE_ANALYTICS_ID = ""
SOCIALACCOUNT_PROVIDERS = {}