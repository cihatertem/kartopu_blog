import ipaddress
import logging
from unittest.mock import MagicMock

from django.test import RequestFactory, TestCase, override_settings

from core.middlewares import TrustedProxyMiddleware


class TrustedProxyMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value="response")
        self.middleware = TrustedProxyMiddleware(self.get_response)

    def test_is_trusted_proxy_no_remote_addr(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        self.assertFalse(self.middleware._is_trusted_proxy(request))

    def test_is_trusted_proxy_no_trusted_nets(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        with override_settings(TRUSTED_PROXY_NETS=[]):
            self.assertFalse(self.middleware._is_trusted_proxy(request))

    def test_is_trusted_proxy_not_in_trusted_nets(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            self.assertFalse(self.middleware._is_trusted_proxy(request))

    def test_is_trusted_proxy_in_trusted_nets(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            self.assertTrue(self.middleware._is_trusted_proxy(request))

    def test_is_trusted_proxy_invalid_ip_logging(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "invalid-ip"

        # Suppress the formatting error by blocking emit in standard logger
        logger = logging.getLogger("core.middlewares")

        # We can capture what args are passed using a custom handler
        class CaptureHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        handler = CaptureHandler()
        logger.addHandler(handler)

        # Disable propagation temporarily to avoid stderr formatting error outputs
        old_propagate = logger.propagate
        logger.propagate = False

        try:
            with override_settings(
                TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]
            ):
                result = self.middleware._is_trusted_proxy(request)

            self.assertFalse(result)
            self.assertEqual(len(handler.records), 1)
            self.assertEqual(
                handler.records[0].msg, "Invalid IP address in proxy check"
            )
            self.assertIsNotNone(handler.records[0].exc_info)
        finally:
            logger.removeHandler(handler)
            logger.propagate = old_propagate

    def test_middleware_call_removes_headers_if_not_trusted(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.10"
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4"
        request.META["HTTP_X_FORWARDED_HOST"] = "example.com"
        request.META["HTTP_X_FORWARDED_PROTO"] = "https"

        with override_settings(TRUSTED_PROXY_NETS=[]):
            response = self.middleware(request)

        self.assertEqual(response, "response")
        self.assertNotIn("HTTP_X_FORWARDED_FOR", request.META)
        self.assertNotIn("HTTP_X_FORWARDED_HOST", request.META)
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", request.META)

    def test_middleware_call_keeps_headers_if_trusted(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4"
        request.META["HTTP_X_FORWARDED_HOST"] = "example.com"
        request.META["HTTP_X_FORWARDED_PROTO"] = "https"

        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            response = self.middleware(request)

        self.assertEqual(response, "response")
        self.assertEqual(request.META.get("HTTP_X_FORWARDED_FOR"), "1.2.3.4")
        self.assertEqual(request.META.get("HTTP_X_FORWARDED_HOST"), "example.com")
        self.assertEqual(request.META.get("HTTP_X_FORWARDED_PROTO"), "https")
