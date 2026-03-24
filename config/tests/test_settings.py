import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import models
from django.db.models.expressions import Expression

from config.settings import get_swarm_secret_for_psg

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


class TestGetSwarmSecretForPsg(TestCase):
    def test_default_value_when_env_not_set(self):
        """Returns the default value if the environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_swarm_secret_for_psg("NON_EXISTENT_KEY", default="my_default")
            self.assertEqual(result, "my_default")

    def test_empty_default_when_env_not_set(self):
        """Returns empty string if the environment variable is not set and no default provided."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_swarm_secret_for_psg("NON_EXISTENT_KEY")
            self.assertEqual(result, "")

    def test_env_value_returned_directly(self):
        """Returns the environment variable value directly if it's not a file path."""
        with patch.dict(os.environ, {"MY_KEY": "my_secret_value"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "my_secret_value")

    def test_env_value_stripped_of_newline(self):
        """Returns the environment variable value stripped of trailing newline."""
        with patch.dict(os.environ, {"MY_KEY": "my_secret_value\n"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "my_secret_value")

    def test_file_content_returned(self):
        """Returns the content of the file if the environment variable is a file path."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write("file_secret_value\n")
            temp_file_path = temp_file.name

        try:
            with patch.dict(os.environ, {"MY_KEY": temp_file_path}):
                result = get_swarm_secret_for_psg("MY_KEY")
                self.assertEqual(result, "file_secret_value")
        finally:
            os.remove(temp_file_path)

    def test_file_content_returned_without_newline_stripping(self):
        """Returns the content of the file without trailing newlines stripped if there are none."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write("file_secret_value")
            temp_file_path = temp_file.name

        try:
            with patch.dict(os.environ, {"MY_KEY": temp_file_path}):
                result = get_swarm_secret_for_psg("MY_KEY")
                self.assertEqual(result, "file_secret_value")
        finally:
            os.remove(temp_file_path)

    def test_multiline_file_content_returns_first_line(self):
        """Returns only the first line of the file if the environment variable is a file path."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write("first_line\nsecond_line\n")
            temp_file_path = temp_file.name

        try:
            with patch.dict(os.environ, {"MY_KEY": temp_file_path}):
                result = get_swarm_secret_for_psg("MY_KEY")
                self.assertEqual(result, "first_line")
        finally:
            os.remove(temp_file_path)
