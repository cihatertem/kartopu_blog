from django.core.cache import caches
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings


@override_settings(RATELIMIT_ENABLE=True, RATELIMIT_USE_CACHE="default")
class NewsletterRateLimitTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.site_settings = SiteSettings.get_settings()
        self.site_settings.is_newsletter_enabled = True
        self.site_settings.save()
        caches["default"].clear()

    def tearDown(self):
        caches["default"].clear()

    def test_subscribe_rate_limit(self):
        url = reverse("newsletter:subscribe_request")
        data = {"email": "test@example.com"}

        # İlk 3 istek başarılı olmalı (yönlendirme yapmalı)
        for i in range(3):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302, f"İstek {i + 1} başarısız.")

        # 4. istek engellenmeli (403 Forbidden)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403, "Rate limit devreye girmedi.")

    def test_unsubscribe_rate_limit(self):
        url = reverse("newsletter:unsubscribe_request")
        data = {"email": "test@example.com"}

        # İlk 3 istek başarılı olmalı (yönlendirme yapmalı)
        for i in range(3):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302, f"İstek {i + 1} başarısız.")

        # 4. istek engellenmeli (403 Forbidden)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 403, "Rate limit devreye girmedi.")
