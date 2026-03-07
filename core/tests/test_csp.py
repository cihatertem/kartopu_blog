import os

from django.test import TestCase, override_settings


@override_settings(SECURE_SSL_REDIRECT=False)
class ContentSecurityPolicyMiddlewareTest(TestCase):
    def setUp(self):
        # Arrange
        self.url = "/"

        # Act
        self.response = self.client.get(self.url)
        self.csp_header = self.response.headers.get("Content-Security-Policy", "")

    def test_csp_header_exists_and_status_200(self):
        # Assert
        self.assertEqual(self.response.status_code, 200)
        self.assertIn("Content-Security-Policy", self.response.headers)

    def test_csp_default_src(self):
        # Assert
        self.assertIn("default-src 'self'", self.csp_header)

    def test_csp_script_src(self):
        # Assert
        self.assertIn("script-src 'strict-dynamic'", self.csp_header)
        self.assertIn("'nonce-", self.csp_header)
        self.assertIn("'self'", self.csp_header)
        self.assertIn("https://static.kartopu.money", self.csp_header)
        self.assertIn("https://www.googletagmanager.com", self.csp_header)

    def test_csp_style_src(self):
        # Assert
        self.assertIn("style-src 'self'", self.csp_header)

    def test_csp_font_src(self):
        # Assert
        self.assertIn("font-src 'self'", self.csp_header)
        self.assertIn("data:", self.csp_header)

    def test_csp_img_src(self):
        # Assert
        self.assertIn("img-src 'self'", self.csp_header)
        self.assertIn("https://pbs.twimg.com", self.csp_header)
        self.assertIn("https://*.googleusercontent.com", self.csp_header)
        self.assertIn("https://*.licdn.com", self.csp_header)

    def test_csp_connect_src(self):
        # Assert
        self.assertIn("connect-src 'self'", self.csp_header)
        self.assertIn("https://www.google-analytics.com", self.csp_header)
        self.assertIn("https://region1.google-analytics.com", self.csp_header)
        self.assertIn("https://api.twitter.com", self.csp_header)
        self.assertIn("https://api.x.com", self.csp_header)

    def test_csp_frame_src(self):
        # Assert
        self.assertIn("frame-src 'self'", self.csp_header)
        self.assertIn("https://platform.twitter.com", self.csp_header)

    def test_csp_worker_src(self):
        # Assert
        self.assertIn("worker-src 'self'", self.csp_header)
        self.assertIn("blob:", self.csp_header)

    def test_csp_form_action(self):
        # Assert
        self.assertIn("form-action 'self'", self.csp_header)
        self.assertIn("https://accounts.google.com", self.csp_header)
        self.assertIn("https://twitter.com", self.csp_header)
        self.assertIn("https://x.com", self.csp_header)
        self.assertIn("https://www.linkedin.com", self.csp_header)

    def test_csp_frame_ancestors(self):
        # Assert
        self.assertIn("frame-ancestors 'self'", self.csp_header)

    def test_csp_object_src(self):
        # Assert
        self.assertIn("object-src 'none'", self.csp_header)

    def test_csp_base_uri(self):
        # Assert
        self.assertIn("base-uri 'self'", self.csp_header)

    def test_csp_upgrade_insecure_requests(self):
        # Assert
        self.assertIn("upgrade-insecure-requests", self.csp_header)


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminCSPExcludeMiddlewareTest(TestCase):
    def test_admin_path_excludes_csp(self):
        # Arrange
        admin_prefix = f"/{os.getenv('ADMIN_ADDRESS', 'admin')}"
        url = f"{admin_prefix}/some-path/"

        # Act
        response = self.client.get(url)

        # Assert
        self.assertNotIn("Content-Security-Policy", response.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", response.headers)

    def test_non_admin_path_includes_csp(self):
        # Arrange
        url = "/"

        # Act
        response = self.client.get(url)

        # Assert
        self.assertIn("Content-Security-Policy", response.headers)
