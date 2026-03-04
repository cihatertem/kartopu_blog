from django.test import SimpleTestCase
from django.urls import resolve, reverse

from core.views import about_view, contact_view, home_view


class CoreUrlsTest(SimpleTestCase):
    def test_home_url_resolves(self):
        url = reverse("core:home")
        self.assertEqual(url, "/")
        self.assertEqual(resolve(url).func, home_view)

    def test_about_url_resolves(self):
        url = reverse("core:about")
        self.assertEqual(url, "/hakkimizda/")
        self.assertEqual(resolve(url).func, about_view)

    def test_contact_url_resolves(self):
        url = reverse("core:contact")
        self.assertEqual(url, "/iletisim/")
        self.assertEqual(resolve(url).func, contact_view)
