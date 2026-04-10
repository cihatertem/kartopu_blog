from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost"])
class NewsletterSecurityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.subscribe_url = reverse("newsletter:subscribe_request")
        self.site_settings = SiteSettings.get_settings()
        self.site_settings.is_newsletter_enabled = True
        self.site_settings.save()

    def test_open_redirect_vulnerability_fixed(self):
        # Malicious referer
        malicious_url = "https://malicious.com"

        # Trigger an invalid form to reach the redirect
        response = self.client.post(
            self.subscribe_url, {"email": "invalid-email"}, HTTP_REFERER=malicious_url
        )

        # Now it should redirect to "/" instead of malicious_url
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_honeypot_redirect_vulnerability_fixed(self):
        malicious_url = "https://malicious.com"

        # Trigger honeypot to reach the redirect
        response = self.client.post(
            self.subscribe_url,
            {"email": "test@example.com", "name": "bot"},
            HTTP_REFERER=malicious_url,
        )

        # Now it should redirect to "/" instead of malicious_url
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_safe_referer_still_works(self):
        # Valid internal referer
        safe_url = "/some-internal-page/"

        response = self.client.post(
            self.subscribe_url, {"email": "invalid-email"}, HTTP_REFERER=safe_url
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, safe_url)
