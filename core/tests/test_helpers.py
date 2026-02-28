import ipaddress

from django.test import RequestFactory, TestCase, override_settings

from core.helpers import client_ip_key, get_client_ip


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
