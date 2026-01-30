from django.test import TestCase
from core.models import SiteSettings
from django.core.cache import cache

class SiteSettingsTest(TestCase):
    def setUp(self):
        cache.clear()
        # Clean up any existing settings just in case
        SiteSettings.objects.all().delete()

    def test_singleton(self):
        SiteSettings.objects.create()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            settings = SiteSettings(is_comments_enabled=False)
            settings.full_clean()
            settings.save()

    def test_get_settings_creates_default(self):
        settings = SiteSettings.get_settings()
        self.assertIsNotNone(settings)
        self.assertTrue(settings.is_comments_enabled)
        self.assertTrue(settings.is_newsletter_enabled)
        self.assertTrue(settings.is_contact_enabled)

    def test_cache_update_on_save(self):
        settings = SiteSettings.get_settings()
        settings.is_comments_enabled = False
        settings.save()

        cached_settings = cache.get("site_settings")
        self.assertFalse(cached_settings.is_comments_enabled)

        settings_from_method = SiteSettings.get_settings()
        self.assertFalse(settings_from_method.is_comments_enabled)
