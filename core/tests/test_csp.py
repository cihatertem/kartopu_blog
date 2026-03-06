import base64
import os
from unittest.mock import patch

from csp.middleware import CSPMiddleware
from django.test import TestCase, override_settings


class CSPMiddlewareTest(TestCase):
    def setUp(self):
        self.url = "/"

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_csp_headers_applied(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200)

        # CSP header should be present
        self.assertIn("Content-Security-Policy", response.headers)

        csp_header = response.headers["Content-Security-Policy"]

        # Check basic directives
        self.assertIn("default-src 'self'", csp_header)
        self.assertIn("script-src 'self'", csp_header)
        self.assertIn("img-src 'self'", csp_header)
        self.assertIn("upgrade-insecure-requests", csp_header)

        # Nonce should be applied to script-src and style-src
        self.assertIn("'nonce-", csp_header)
