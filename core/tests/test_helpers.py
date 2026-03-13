import ipaddress

from django.test import RequestFactory, TestCase, override_settings

from core.helpers import client_ip_key, get_client_ip, normalize_search_query


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
        """Should lowercase and split words >= 3 chars."""
        self.assertEqual(
            normalize_search_query("Python Django Framework"),
            ["python", "django", "framework"],
        )

    def test_filters_short_words(self):
        """Should remove words with length < 3."""
        self.assertEqual(
            normalize_search_query("A an the in on at to JS"),
            ["the"],
        )

    def test_all_short_words(self):
        """Should return empty list if all words are < 3 chars."""
        self.assertEqual(
            normalize_search_query("I do go up to my PC"),
            [],
        )

    def test_empty_string(self):
        """Should handle empty string."""
        self.assertEqual(
            normalize_search_query(""),
            [],
        )

    def test_whitespace_only(self):
        """Should handle string with only whitespaces."""
        self.assertEqual(
            normalize_search_query("   \t\n  "),
            [],
        )

    def test_numbers_and_punctuation(self):
        """Should treat numbers and punctuation as parts of tokens."""
        self.assertEqual(
            normalize_search_query("C++ C# .NET v2.0 123"),
            ["c++", ".net", "v2.0", "123"],
        )
