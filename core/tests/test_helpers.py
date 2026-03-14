import ipaddress

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

        with self.assertRaises(ValueError):
            get_client_ip(request)

    def test_client_ip_key_with_ip(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        self.assertEqual(client_ip_key("test_group", request), "192.168.1.10")

    def test_client_ip_key_without_ip(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        self.assertEqual(client_ip_key("test_group", request), "unknown")


class NormalizeSearchQueryTest(TestCase):
    def test_normal_case(self):
        """Should return stripped string."""
        self.assertEqual(
            normalize_search_query(" Python Django Framework "),
            "Python Django Framework",
        )

    def test_preserves_quotes_and_negations(self):
        """Should preserve quotes and minuses."""
        self.assertEqual(
            normalize_search_query('"finansal özgürlük" -vergi'),
            '"finansal özgürlük" -vergi',
        )

    def test_empty_string(self):
        """Should handle empty string."""
        self.assertEqual(
            normalize_search_query(""),
            "",
        )

    def test_whitespace_only(self):
        """Should handle string with only whitespaces."""
        self.assertEqual(
            normalize_search_query("   \t\n  "),
            "",
        )


class CaptchaIsValidTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_captcha(self):
        """Should return True when POST captcha matches session captcha."""
        request = self.factory.post("/", {"captcha": "15"})
        request.session = {CAPTCHA_SESSION_KEY: "15"}
        self.assertTrue(captcha_is_valid(request))

    def test_invalid_captcha(self):
        """Should return False when POST captcha does not match session captcha."""
        request = self.factory.post("/", {"captcha": "12"})
        request.session = {CAPTCHA_SESSION_KEY: "15"}
        self.assertFalse(captcha_is_valid(request))

    def test_missing_post_captcha(self):
        """Should return False when POST captcha is missing."""
        request = self.factory.post("/")
        request.session = {CAPTCHA_SESSION_KEY: "15"}
        self.assertFalse(captcha_is_valid(request))

    def test_missing_session_captcha(self):
        """Should return False when session captcha is missing."""
        request = self.factory.post("/", {"captcha": "15"})
        request.session = {}
        self.assertFalse(captcha_is_valid(request))

    def test_both_missing(self):
        """Should return False when both POST and session captchas are missing."""
        request = self.factory.post("/")
        request.session = {}
        self.assertFalse(captcha_is_valid(request))

    def test_non_integer_captcha(self):
        """Should return False when POST captcha is not an integer."""
        request = self.factory.post("/", {"captcha": "abc"})
        request.session = {CAPTCHA_SESSION_KEY: "15"}
        with self.assertLogs("core.helpers", level="ERROR"):
            self.assertFalse(captcha_is_valid(request))

    def test_non_integer_session(self):
        """Should return False when session captcha is not an integer."""
        request = self.factory.post("/", {"captcha": "15"})
        request.session = {CAPTCHA_SESSION_KEY: "abc"}
        with self.assertLogs("core.helpers", level="ERROR"):
            self.assertFalse(captcha_is_valid(request))

    def test_both_non_integer(self):
        """Should return False when both captchas are not integers."""
        request = self.factory.post("/", {"captcha": "abc"})
        request.session = {CAPTCHA_SESSION_KEY: "abc"}
        with self.assertLogs("core.helpers", level="ERROR"):
            self.assertFalse(captcha_is_valid(request))


class GenerateCaptchaTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_generate_captcha(self):
        """Should return two integers between 1 and 10 and set session correctly."""
        request = self.factory.get("/")
        request.session = {}

        num_one, num_two = _generate_captcha(request)

        self.assertIsInstance(num_one, int)
        self.assertIsInstance(num_two, int)
        self.assertGreaterEqual(num_one, 1)
        self.assertLessEqual(num_one, 10)
        self.assertGreaterEqual(num_two, 1)
        self.assertLessEqual(num_two, 10)

        self.assertIn(CAPTCHA_SESSION_KEY, request.session)
        self.assertEqual(request.session[CAPTCHA_SESSION_KEY], num_one + num_two)
