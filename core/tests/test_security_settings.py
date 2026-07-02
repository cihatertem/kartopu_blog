import importlib
import os

from django.test import SimpleTestCase


class AllowedHostsSecurityTest(SimpleTestCase):
    def setUp(self):
        self.original_debug = os.environ.get("DJANGO_DEBUG")
        self.original_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS")

    def tearDown(self):
        if self.original_debug is not None:
            os.environ["DJANGO_DEBUG"] = self.original_debug
        elif "DJANGO_DEBUG" in os.environ:
            del os.environ["DJANGO_DEBUG"]

        if self.original_hosts is not None:
            os.environ["DJANGO_ALLOWED_HOSTS"] = self.original_hosts
        elif "DJANGO_ALLOWED_HOSTS" in os.environ:
            del os.environ["DJANGO_ALLOWED_HOSTS"]

    def test_allowed_hosts_in_debug_mode_without_env_var(self):
        os.environ["DJANGO_DEBUG"] = "1"
        if "DJANGO_ALLOWED_HOSTS" in os.environ:
            del os.environ["DJANGO_ALLOWED_HOSTS"]

        import config.settings

        importlib.reload(config.settings)

        self.assertNotIn("*", config.settings.ALLOWED_HOSTS)
        self.assertIn("localhost", config.settings.ALLOWED_HOSTS)
        self.assertIn("127.0.0.1", config.settings.ALLOWED_HOSTS)
        self.assertIn("[::1]", config.settings.ALLOWED_HOSTS)

    def test_allowed_hosts_in_debug_mode_with_env_var(self):
        os.environ["DJANGO_DEBUG"] = "1"
        os.environ["DJANGO_ALLOWED_HOSTS"] = "dev.local,test.local"

        import config.settings

        importlib.reload(config.settings)

        self.assertEqual(config.settings.ALLOWED_HOSTS, ["dev.local", "test.local"])

    def test_allowed_hosts_in_production_mode_without_env_var(self):
        os.environ["DJANGO_DEBUG"] = "0"
        if "DJANGO_ALLOWED_HOSTS" in os.environ:
            del os.environ["DJANGO_ALLOWED_HOSTS"]

        import config.settings

        importlib.reload(config.settings)

        self.assertEqual(config.settings.ALLOWED_HOSTS, [""])

    def test_allowed_hosts_in_production_mode_with_env_var(self):
        os.environ["DJANGO_DEBUG"] = "0"
        os.environ["DJANGO_ALLOWED_HOSTS"] = "example.com"

        import config.settings

        importlib.reload(config.settings)

        self.assertEqual(config.settings.ALLOWED_HOSTS, ["example.com"])


class CacheKeySecurityTest(SimpleTestCase):
    def test_secure_cache_key_hides_ratelimit_identifier(self):
        from config.cache_keys import secure_cache_key

        raw_key = "rl:newsletter:subscribe:ip:203.0.113.42"
        generated_key = secure_cache_key(raw_key, "kartopu_blog", 1)

        self.assertNotIn(raw_key, generated_key)
        self.assertNotIn("203.0.113.42", generated_key)
        self.assertTrue(generated_key.startswith("kartopu_blog:1:"))
        self.assertEqual(generated_key, secure_cache_key(raw_key, "kartopu_blog", 1))

    def test_debug_cache_is_not_persistent_database_cache(self):
        os.environ["DJANGO_DEBUG"] = "1"

        import config.settings

        importlib.reload(config.settings)

        default_cache = config.settings.CACHES["default"]
        self.assertEqual(
            default_cache["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )
        self.assertNotEqual(
            default_cache["BACKEND"],
            "django.core.cache.backends.db.DatabaseCache",
        )
        self.assertEqual(
            default_cache["KEY_FUNCTION"],
            "config.cache_keys.secure_cache_key",
        )
