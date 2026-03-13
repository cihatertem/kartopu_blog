from unittest.mock import patch

from django.test import TestCase

from newsletter.services import (
    build_subscribe_confirm_url,
    build_unsubscribe_url,
    send_subscribe_confirmation,
)
from newsletter.tokens import parse_token


class ServicesTest(TestCase):
    @patch("newsletter.services.send_templated_email")
    @patch("newsletter.services.build_unsubscribe_url")
    @patch("newsletter.services.build_subscribe_confirm_url")
    def test_send_subscribe_confirmation(
        self, mock_build_confirm, mock_build_unsub, mock_send
    ):
        mock_build_confirm.return_value = "http://testserver/confirm"
        mock_build_unsub.return_value = "http://testserver/unsubscribe"

        email = "test@example.com"
        send_subscribe_confirmation(email)

        mock_build_confirm.assert_called_once_with(email)
        mock_build_unsub.assert_called_once_with(email)

        expected_context = {
            "confirm_url": "http://testserver/confirm",
            "unsubscribe_url": "http://testserver/unsubscribe",
            "site_name": "Kartopu Money",
        }

        mock_send.assert_called_once_with(
            subject="Newsletter aboneliğinizi onaylayın",
            to_email=email,
            template_prefix="subscribe_confirm",
            context=expected_context,
        )

    def test_build_subscribe_confirm_url(self):
        email = "test@example.com"
        url = build_subscribe_confirm_url(email)

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
        self.assertEqual(payload["action"], "subscribe")

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
