from django.test import TestCase

from newsletter.services import build_unsubscribe_url
from newsletter.tokens import parse_token


class ServicesTest(TestCase):
    def test_build_unsubscribe_url(self):
        email = "test@example.com"
        url = build_unsubscribe_url(email)

        # Check that it returns an absolute URL
        self.assertTrue(url.startswith("http://") or url.startswith("https://"))

        # Extract the path and token
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        # The path should match the reverse of confirm url with some token
        self.assertTrue(path.startswith("/newsletter/confirm/"))

        # Extract token from the path
        # Path is like: /newsletter/confirm/<token>/
        # Split by '/' -> ['', 'newsletter', 'confirm', '<token>', '']
        parts = path.strip("/").split("/")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "newsletter")
        self.assertEqual(parts[1], "confirm")

        token = parts[2]

        # Verify the token payload
        payload = parse_token(token, max_age=86400)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["action"], "unsubscribe")
