from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User


class AccountsIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="integration@example.com", password="password"
        )

    def test_author_profile_access(self):
        # Arrange
        self.client.force_login(self.user)
        url = reverse("accounts:author_profile")

        # Act
        response = self.client.get(url, follow=True)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertInHTML("Author Profile", response.content.decode())
