from django.test import SimpleTestCase
from django.urls import resolve, reverse

from accounts import views


class AccountsURLsTests(SimpleTestCase):
    def test_author_profile_url_resolves(self):
        url = reverse("accounts:author_profile")

        resolver_match = resolve(url)

        self.assertEqual(resolver_match.func, views.author_profile_view)
