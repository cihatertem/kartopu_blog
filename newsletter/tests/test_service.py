from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from newsletter.services import (
    build_subscribe_confirm_url,
    build_unsubscribe_url,
    prepare_templated_email,
    send_subscribe_confirmation,
    send_templated_email,
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

        self.assertTrue(url.startswith("http://") or url.startswith("https://"))

        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        self.assertTrue(path.startswith("/newsletter/confirm/"))

        parts = path.strip("/").split("/")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "newsletter")
        self.assertEqual(parts[1], "confirm")

        token = parts[2]

        payload = parse_token(token, max_age=86400)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["action"], "subscribe")

    def test_build_unsubscribe_url(self):
        email = "test@example.com"
        url = build_unsubscribe_url(email)

        self.assertTrue(url.startswith("http://") or url.startswith("https://"))

        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        self.assertTrue(path.startswith("/newsletter/confirm/"))

        parts = path.strip("/").split("/")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "newsletter")
        self.assertEqual(parts[1], "confirm")

        token = parts[2]

        payload = parse_token(token, max_age=86400)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["action"], "unsubscribe")

    @patch("newsletter.services.render_to_string")
    def test_prepare_templated_email(self, mock_render):
        def render_side_effect(template_name, context):
            if template_name.endswith(".txt"):
                return "Mock text body"
            elif template_name.endswith(".html"):
                return "Mock html body"
            return "Unknown"

        mock_render.side_effect = render_side_effect

        context = {"key": "value"}
        result = prepare_templated_email(
            subject="Test Subject",
            to_email="test@example.com",
            template_prefix="test_template",
            context=context,
        )

        self.assertEqual(result["subject"], "Test Subject")
        self.assertEqual(result["to_email"], "test@example.com")
        self.assertIn("Kartopu.Money Blog", result["from_email"])
        self.assertEqual(result["text_body"], "Mock text body")
        self.assertEqual(result["html_body"], "Mock html body")

        self.assertEqual(mock_render.call_count, 2)
        mock_render.assert_any_call("newsletter/email/test_template.txt", context)
        mock_render.assert_any_call("newsletter/email/test_template.html", context)

    @patch("newsletter.services.prepare_templated_email")
    def test_send_templated_email(self, mock_prepare):
        mock_prepare.return_value = {
            "subject": "Test Subject",
            "text_body": "Text body content",
            "html_body": "<html>Html body content</html>",
            "from_email": '"Kartopu" <test@kartopu.money>',
            "to_email": "recipient@example.com",
        }

        mail.outbox = []

        send_templated_email(
            subject="Ignored by mock",
            to_email="ignored@example.com",
            template_prefix="ignored",
            context={},
        )

        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "Test Subject")
        self.assertEqual(sent_email.body, "Text body content")
        self.assertEqual(sent_email.from_email, '"Kartopu" <test@kartopu.money>')
        self.assertEqual(sent_email.to, ["recipient@example.com"])

        self.assertEqual(len(sent_email.alternatives), 1)
        self.assertEqual(
            sent_email.alternatives[0], ("<html>Html body content</html>", "text/html")
        )
