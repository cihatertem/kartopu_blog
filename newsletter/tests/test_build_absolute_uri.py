from django.test import TestCase, override_settings

from newsletter.services import build_absolute_uri


class BuildAbsoluteURITest(TestCase):
    @override_settings(SITE_BASE_URL="https://test.example.com")
    def test_absolute_uri_returned_as_is(self):
        """Test that fully qualified URLs are returned unmodified."""
        path = "https://external.com/some/path/?q=1"
        self.assertEqual(build_absolute_uri(path), path)

        path2 = "http://another.site.org/resource"
        self.assertEqual(build_absolute_uri(path2), path2)

    @override_settings(SITE_BASE_URL="https://test.example.com")
    def test_protocol_relative_uri(self):
        """Test that protocol-relative URLs use the scheme from get_site_base_url()."""
        path = "//cdn.example.com/image.png"
        self.assertEqual(build_absolute_uri(path), "https://cdn.example.com/image.png")

    @override_settings(SITE_BASE_URL="http://insecure.example.com")
    def test_protocol_relative_uri_http(self):
        """Test that protocol-relative URLs use the HTTP scheme if the base URL is HTTP."""
        path = "//cdn.example.com/image.png"
        self.assertEqual(build_absolute_uri(path), "http://cdn.example.com/image.png")

    @override_settings(SITE_BASE_URL="https://test.example.com/")
    def test_relative_path(self):
        """Test that relative paths are correctly appended to the base URL."""
        # Function strips trailing slash from base url and leading slash from path
        path = "/about-us/"
        self.assertEqual(build_absolute_uri(path), "https://test.example.com/about-us/")

        path_no_slash = "contact/"
        self.assertEqual(
            build_absolute_uri(path_no_slash), "https://test.example.com/contact/"
        )

    @override_settings(SITE_BASE_URL="")
    def test_fallback_to_site_framework(self):
        """Test fallback when SITE_BASE_URL is empty."""
        from django.contrib.sites.models import Site

        site = Site.objects.get_current()
        site.domain = "site.framework.com"
        site.save()

        path = "/api/v1/resource"
        # When DEBUG is false (default in tests unless overriden), protocol is https
        self.assertEqual(
            build_absolute_uri(path), "https://site.framework.com/api/v1/resource"
        )

        # Test protocol-relative with Site fallback
        self.assertEqual(
            build_absolute_uri("//external.com/script.js"),
            "https://external.com/script.js",
        )
