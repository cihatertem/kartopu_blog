import secrets

from django.db import models
from django.db.models.expressions import Expression

from config.settings import *

SECRET_KEY = secrets.token_urlsafe(50)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Bypass migrations that use PostgreSQL-specific features
MIGRATION_MODULES = {
    "blog": None,
    "accounts": None,
    "core": None,
    "newsletter": None,
    "portfolio": None,
    "comments": None,
    "redirects": None,
    "socialaccount": None,
    "account": None,
}

# Monkeypatch GinIndex and SearchVector for SQLite tests


class MockGinIndex(models.Index):
    def __init__(self, *args, **kwargs):
        kwargs.pop("config", None)
        super().__init__(*args, **kwargs)

    def create_sql(self, model, schema_editor, using=""):  # pyright: ignore[reportIncompatibleMethodOverride]
        return ""


try:
    import django.contrib.postgres.indexes

    django.contrib.postgres.indexes.GinIndex = MockGinIndex
except ImportError:
    pass


class MockSearchVector(Expression):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def resolve_expression(self, *args, **kwargs):
        return self


try:
    import django.contrib.postgres.search

    django.contrib.postgres.search.SearchVector = MockSearchVector
except ImportError:
    pass
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "[::1]"]
SECURE_SSL_REDIRECT = False
