import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import models
from django.db.models.expressions import Expression

from config.settings import *

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
    "sites": None,
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


django.contrib.postgres.indexes.GinIndex = MockGinIndex


class MockSearchVector(Expression):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def resolve_expression(self, *args, **kwargs):
        return self


django.contrib.postgres.search.SearchVector = MockSearchVector
ALLOWED_HOSTS = ["*"]
