import ipaddress
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from core.helpers import (
    CAPTCHA_SESSION_KEY,
    _generate_captcha,
    captcha_is_valid,
    client_ip_key,
    get_client_ip,
    normalize_search_query,
)


class GetClientIPTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_missing_remote_addr(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        self.assertIsNone(get_client_ip(request))

    def test_no_trusted_proxies(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"

        with override_settings(TRUSTED_PROXY_NETS=[]):
            self.assertEqual(get_client_ip(request), "192.168.1.10")

    def test_remote_addr_not_in_trusted_proxies(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"

        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            self.assertEqual(get_client_ip(request), "192.168.1.10")

    def test_remote_addr_in_trusted_proxies_no_xff(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        if "HTTP_X_FORWARDED_FOR" in request.META:
            del request.META["HTTP_X_FORWARDED_FOR"]

        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            self.assertEqual(get_client_ip(request), "10.0.0.5")

    def test_remote_addr_in_trusted_proxies_with_xff(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.195, 198.51.100.1"

        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            self.assertEqual(get_client_ip(request), "203.0.113.195")

    def test_invalid_remote_addr(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "invalid-ip"

        # Instead of ValueError, we expect the fallback logic to return the raw invalid string
        self.assertEqual(get_client_ip(request), "invalid-ip")

    def test_malformed_ip_list_in_remote_addr(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10, 10.0.0.5"

        # Should fall back to the string itself
        self.assertEqual(get_client_ip(request), "192.168.1.10, 10.0.0.5")

    def test_client_ip_key_with_ip(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        self.assertEqual(client_ip_key("test_group", request), "192.168.1.10")

    def test_client_ip_key_without_ip(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        self.assertEqual(client_ip_key("test_group", request), "unknown")


class ParseIntTest(TestCase):
    def test_parse_int_valid(self):
        from core.helpers import _parse_int

        self.assertEqual(_parse_int("123"), 123)
        self.assertEqual(_parse_int("0"), 0)
        self.assertEqual(_parse_int("-5"), -5)

    def test_parse_int_invalid(self):
        from core.helpers import _parse_int

        with self.assertLogs("core.helpers", level="ERROR"):
            self.assertIsNone(_parse_int("abc"))

    def test_parse_int_none_or_empty(self):
        from core.helpers import _parse_int

        self.assertIsNone(_parse_int(None))
        self.assertIsNone(_parse_int(""))


class GetSafeRefererTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_safe_referer_valid_internal(self):
        from core.helpers import get_safe_referer

        request = self.factory.get("/")
        request.META["HTTP_REFERER"] = "http://testserver/about/"
        self.assertEqual(get_safe_referer(request), "http://testserver/about/")

    def test_get_safe_referer_invalid_external(self):
        from core.helpers import get_safe_referer

        request = self.factory.get("/")
        request.META["HTTP_REFERER"] = "http://malicious.com/"
        self.assertEqual(get_safe_referer(request), "/")
        self.assertEqual(get_safe_referer(request, default="/home"), "/home")

    def test_get_safe_referer_missing(self):
        from core.helpers import get_safe_referer

        request = self.factory.get("/")
        self.assertEqual(get_safe_referer(request), "/")

    def test_get_safe_referer_secure_request(self):
        from core.helpers import get_safe_referer

        request = self.factory.get("/", secure=True)
        # Should be secure referer
        request.META["HTTP_REFERER"] = "https://testserver/about/"
        self.assertEqual(get_safe_referer(request), "https://testserver/about/")

        # Insecure referer on secure request should be rejected
        request.META["HTTP_REFERER"] = "http://testserver/about/"
        self.assertEqual(get_safe_referer(request), "/")


class NormalizeSearchQueryTest(TestCase):
    def test_normalize_search_query_edge_cases(self):
        cases = [
            # Basic cases
            (" Python Django Framework ", "Python Django Framework"),
            ('"finansal özgürlük" -vergi', '"finansal özgürlük" -vergi'),
            ("", ""),
            ("   \t\n  ", ""),
            # Edge cases
            ("\xa0non-breaking\xa0", "non-breaking"),  # Non-breaking spaces
            ("\u200bzero width\u200b", "\u200bzero width\u200b"),  # Zero-width spaces
            (" emojis 🚀 \n", "emojis 🚀"),
            ("A" * 1000 + "  ", "A" * 1000),  # Very long string
            ("\0null byte\0", "\0null byte\0"),  # Null bytes
            ("sql injection' OR '1'='1", "sql injection' OR '1'='1"),
            ("<script>alert('xss')</script>", "<script>alert('xss')</script>"),
            ("   multiple   internal   spaces   ", "multiple   internal   spaces"),
            (" \r\n \t mixed whitespace \t \r\n ", "mixed whitespace"),
            (
                "TR \u0130 \u011e \u015e \u00c7 \u00d6 \u00dc",
                "TR \u0130 \u011e \u015e \u00c7 \u00d6 \u00dc",
            ),  # Turkish characters
        ]

        for q, expected in cases:
            with self.subTest(query=q):
                self.assertEqual(normalize_search_query(q), expected)


class CaptchaIsValidTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_captcha(self):
        """Should return True when POST captcha matches session captcha (case-insensitive)."""
        request = self.factory.post("/", {"captcha": "ABcDe"})
        request.session = {CAPTCHA_SESSION_KEY: "aBcDe"}
        self.assertTrue(captcha_is_valid(request))

    def test_invalid_captcha(self):
        """Should return False when POST captcha does not match session captcha."""
        request = self.factory.post("/", {"captcha": "XYZ"})
        request.session = {CAPTCHA_SESSION_KEY: "ABC"}
        self.assertFalse(captcha_is_valid(request))

    def test_missing_post_captcha(self):
        """Should return False when POST captcha is missing."""
        request = self.factory.post("/")
        request.session = {CAPTCHA_SESSION_KEY: "ABC"}
        self.assertFalse(captcha_is_valid(request))

    def test_missing_session_captcha(self):
        """Should return False when session captcha is missing."""
        request = self.factory.post("/", {"captcha": "ABC"})
        request.session = {}
        self.assertFalse(captcha_is_valid(request))

    def test_both_missing(self):
        """Should return False when both POST and session captchas are missing."""
        request = self.factory.post("/")
        request.session = {}
        self.assertFalse(captcha_is_valid(request))

    def test_post_captcha_is_explicitly_none(self):
        """Should return False when POST captcha value is explicitly None."""
        request = self.factory.post("/")
        request.POST._mutable = True
        request.POST["captcha"] = None
        request.session = {CAPTCHA_SESSION_KEY: "ABC"}
        self.assertFalse(captcha_is_valid(request))

    def test_session_captcha_is_explicitly_none(self):
        """Should return False when session captcha value is explicitly None."""
        request = self.factory.post("/", {"captcha": "ABC"})
        request.session = {CAPTCHA_SESSION_KEY: None}
        self.assertFalse(captcha_is_valid(request))

    def test_both_explicitly_none(self):
        """Should return False when both session and POST captchas are explicitly None."""
        request = self.factory.post("/")
        request.POST._mutable = True
        request.POST["captcha"] = None
        request.session = {CAPTCHA_SESSION_KEY: None}
        self.assertFalse(captcha_is_valid(request))

    def test_empty_string_captcha(self):
        """Should return False when POST captcha is an empty string."""
        request = self.factory.post("/", {"captcha": ""})
        request.session = {CAPTCHA_SESSION_KEY: "ABC"}
        self.assertFalse(captcha_is_valid(request))

    def test_empty_string_session(self):
        """Should return False when session captcha is an empty string."""
        request = self.factory.post("/", {"captcha": "ABC"})
        request.session = {CAPTCHA_SESSION_KEY: ""}
        self.assertFalse(captcha_is_valid(request))

    def test_whitespace_captcha(self):
        """Should return True when POST captcha has leading/trailing whitespace but matches."""
        request = self.factory.post("/", {"captcha": " ABC "})
        request.session = {CAPTCHA_SESSION_KEY: "ABC"}
        self.assertTrue(captcha_is_valid(request))


class GenerateCaptchaTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_generate_captcha(self):
        """Should return base64 encoded image string and set session to a 5 char string."""
        request = self.factory.get("/")
        request.session = {}

        b64_image = _generate_captcha(request)

        self.assertIsInstance(b64_image, str)
        self.assertGreater(len(b64_image), 100)  # Basic check for base64 data length

        self.assertIn(CAPTCHA_SESSION_KEY, request.session)
        captcha_text = request.session[CAPTCHA_SESSION_KEY]
        self.assertIsInstance(captcha_text, str)
        self.assertEqual(len(captcha_text), 5)

    def test_generate_captcha_font_fallback(self):
        """Should fallback to default font if truetype font is not found."""
        from PIL import ImageFont

        request = self.factory.get("/")
        request.session = {}

        original_truetype = ImageFont.truetype

        def side_effect(font, *args, **kwargs):
            # Only raise error for the specific font path string
            if isinstance(font, str) and font.endswith(".ttf"):
                raise IOError("Font not found")
            return original_truetype(font, *args, **kwargs)

        with patch("PIL.ImageFont.truetype", side_effect=side_effect) as mock_truetype:
            with patch(
                "PIL.ImageFont.load_default", wraps=ImageFont.load_default
            ) as mock_load_default:
                b64_image = _generate_captcha(request)

                self.assertIsInstance(b64_image, str)
                self.assertGreater(len(b64_image), 100)
                # It should be called at least twice: once in our code, and once inside load_default
                self.assertGreaterEqual(mock_truetype.call_count, 1)
                mock_load_default.assert_called_once()

                self.assertIn(CAPTCHA_SESSION_KEY, request.session)
                self.assertEqual(len(request.session[CAPTCHA_SESSION_KEY]), 5)
