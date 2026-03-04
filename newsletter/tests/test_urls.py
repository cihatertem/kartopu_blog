from django.test import TestCase
from django.urls import resolve, reverse

from newsletter import views


class NewsletterURLsTest(TestCase):
    def test_subscribe_url_resolves(self):
        url = reverse("newsletter:subscribe_request")
        self.assertEqual(url, "/newsletter/subscribe/")
        self.assertEqual(resolve(url).func, views.subscribe_request)

    def test_unsubscribe_url_resolves(self):
        url = reverse("newsletter:unsubscribe_request")
        self.assertEqual(url, "/newsletter/unsubscribe/")
        self.assertEqual(resolve(url).func, views.unsubscribe_request)

    def test_confirm_url_resolves(self):
        url = reverse("newsletter:confirm", kwargs={"token": "some-token"})
        self.assertEqual(url, "/newsletter/confirm/some-token/")
        self.assertEqual(resolve(url).func, views.confirm_subscription)
