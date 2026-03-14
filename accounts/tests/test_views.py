from django.test import Client, TestCase, override_settings
from django.urls import reverse


class AccountsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_author_profile_view(self):
        url = reverse("accounts:author_profile")

        response = self.client.get(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Author Profile")

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_disabled_account_view(self):
        url = reverse("account_login_disabled")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Account Feature Disabled", status_code=404)
