import ipaddress
import logging
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings

from core.middlewares import (
    AdminCSPExcludeMiddleware,
    HealthCheckMiddleware,
    RejectNullByteMiddleware,
    TrustedProxyMiddleware,
)


class RejectNullByteMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value="response")
        self.middleware = RejectNullByteMiddleware(self.get_response)

    def test_clean_path_passes_through(self):
        request = self.factory.get("/blog/")
        response = self.middleware(request)

        self.assertEqual(response, "response")
        self.get_response.assert_called_once_with(request)

    def test_null_byte_in_path_returns_400(self):
        request = self.factory.get("/clean/")
        request.META["PATH_INFO"] = "/.env\x00.html"
        response = self.middleware(request)

        self.assertEqual(response.status_code, 400)
        self.get_response.assert_not_called()

    def test_null_byte_in_query_string_returns_400(self):
        request = self.factory.get("/clean/")
        request.META["QUERY_STRING"] = "q=\x00"
        response = self.middleware(request)

        self.assertEqual(response.status_code, 400)
        self.get_response.assert_not_called()


class HealthCheckMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = HealthCheckMiddleware(lambda r: "response")

    def test_process_request_ping(self):
        request = self.factory.get("/ping")
        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"response": "pong!"}')

    def test_process_request_other_path(self):
        request = self.factory.get("/")
        response = self.middleware.process_request(request)

        self.assertIsNone(response)

    def test_health_check_ping(self):
        request = self.factory.get("/ping")
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"response": "pong!"}')

    def test_health_check_other_path(self):
        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertEqual(response, "response")


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

        logger = logging.getLogger("core.middlewares")

        class CaptureHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        handler = CaptureHandler()
        logger.addHandler(handler)

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


class AdminCSPExcludeMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _get_mocked_get_response(self):
        from django.http import HttpResponse

        def get_response(request):
            response = HttpResponse("dummy")
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            response.headers["Content-Security-Policy-Report-Only"] = (
                "default-src 'self'"
            )
            response.headers["Other-Header"] = "Keep-Me"
            return response

        return get_response

    @patch.dict("os.environ", {"ADMIN_ADDRESS": "admin"})
    def test_removes_csp_headers_on_admin_path(self):
        middleware = AdminCSPExcludeMiddleware(self._get_mocked_get_response())
        request = self.factory.get("/admin/")
        response = middleware(request)

        self.assertNotIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)
        self.assertEqual(response.headers.get("Other-Header"), "Keep-Me")

    @patch.dict("os.environ", {"ADMIN_ADDRESS": "admin"})
    def test_removes_csp_headers_on_en_admin_path(self):
        middleware = AdminCSPExcludeMiddleware(self._get_mocked_get_response())
        request = self.factory.get("/en/admin/")
        response = middleware(request)

        self.assertNotIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)

    @patch.dict("os.environ", {"ADMIN_ADDRESS": "admin"})
    def test_removes_csp_headers_on_tr_admin_path(self):
        middleware = AdminCSPExcludeMiddleware(self._get_mocked_get_response())
        request = self.factory.get("/tr/admin/")
        response = middleware(request)

        self.assertNotIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)

    @patch.dict("os.environ", {"ADMIN_ADDRESS": "admin"})
    def test_keeps_csp_headers_on_non_admin_path(self):
        middleware = AdminCSPExcludeMiddleware(self._get_mocked_get_response())
        request = self.factory.get("/about/")
        response = middleware(request)

        self.assertEqual(
            response.headers.get("Content-Security-Policy"), "default-src 'self'"
        )
        self.assertEqual(
            response.headers.get("Content-Security-Policy-Report-Only"),
            "default-src 'self'",
        )

    @patch("os.getenv")
    def test_handles_custom_admin_prefix(self, mock_getenv):
        mock_getenv.return_value = "custom-admin"

        middleware = AdminCSPExcludeMiddleware(self._get_mocked_get_response())
        request = self.factory.get("/custom-admin/")
        response = middleware(request)

        self.assertNotIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)

        # Now verify non-admin paths with this setup
        request2 = self.factory.get("/admin/")
        response2 = middleware(request2)

        self.assertEqual(
            response2.headers.get("Content-Security-Policy"), "default-src 'self'"
        )
        self.assertEqual(
            response2.headers.get("Content-Security-Policy-Report-Only"),
            "default-src 'self'",
        )
