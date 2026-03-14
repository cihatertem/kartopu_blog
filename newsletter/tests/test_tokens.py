from django.core import signing
from django.test import TestCase

from newsletter.tokens import make_token, parse_token


class TokenTests(TestCase):
    def test_make_token(self):
        email = "test@example.com"
        action = "subscribe"
        token = make_token(email, action)

        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

        payload = parse_token(token, max_age=3600)
        self.assertEqual(payload, {"email": email, "action": action})

    def test_parse_token_success(self):
        email = "test@example.com"
        action = "subscribe"
        token = make_token(email, action)

        payload = parse_token(token, max_age=3600)
        self.assertEqual(payload, {"email": email, "action": action})

    def test_parse_token_expired(self):
        email = "test@example.com"
        action = "subscribe"
        token = make_token(email, action)

        with self.assertRaises(signing.SignatureExpired):
            parse_token(token, max_age=-1)

    def test_parse_token_invalid_signature(self):
        email = "test@example.com"
        action = "subscribe"
        token = make_token(email, action)

        invalid_token = token[:-1] + ("a" if token[-1] != "a" else "b")

        with self.assertRaises(signing.BadSignature):
            parse_token(invalid_token, max_age=3600)
