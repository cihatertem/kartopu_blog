from django.test import SimpleTestCase
from django.urls import resolve, reverse

from accounts import views


class AccountsURLsTests(SimpleTestCase):
    def test_author_profile_url_resolves(self):
        # Arrange
        url = reverse("accounts:author_profile")

        # Act
        resolver_match = resolve(url)

        # Assert
        self.assertEqual(resolver_match.func, views.author_profile_view)
