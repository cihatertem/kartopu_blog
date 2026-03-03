from django.test import Client, TestCase
from django.urls import reverse


class AccountsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_author_profile_view(self):
        # Arrange
        url = reverse("accounts:author_profile")

        # Act
        response = self.client.get(url, follow=True)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Author Profile Page")

    def test_disabled_account_view(self):
        # Arrange
        from django.http import Http404

        from accounts.views import disabled_account_view

        # Act & Assert
        with self.assertRaises(Http404):
            disabled_account_view(None)
