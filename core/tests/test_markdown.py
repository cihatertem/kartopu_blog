from django.test import TestCase, override_settings

from core.markdown import render_markdown, set_link_attributes


class MarkdownTests(TestCase):
    # --- set_link_attributes ---
    def test_set_link_attributes_no_href(self):
        # Arrange
        attrs = {(None, "title"): "Test"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        self.assertEqual(result, attrs)

    def test_set_link_attributes_internal_relative_link(self):
        # Arrange
        attrs = {(None, "href"): "/about/", (None, "rel"): "nofollow"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        # Internal links should NOT have "nofollow"
        self.assertNotIn((None, "rel"), result)

    def test_set_link_attributes_internal_anchor_link(self):
        # Arrange
        attrs = {(None, "href"): "#top"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        self.assertNotIn((None, "rel"), result)

    @override_settings(SITE_BASE_URL="https://example.com")
    def test_set_link_attributes_internal_absolute_link(self):
        # Arrange
        attrs = {(None, "href"): "https://example.com/blog/"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        # Internal links (matching domain) should NOT have nofollow
        self.assertNotIn((None, "rel"), result)

    @override_settings(SITE_BASE_URL="https://example.com")
    def test_set_link_attributes_external_link(self):
        # Arrange
        attrs = {(None, "href"): "https://external.com/page/"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        # External links MUST have nofollow
        self.assertIn((None, "rel"), result)
        self.assertEqual(result[(None, "rel")], "nofollow")

    def test_set_link_attributes_external_link_preserves_rel(self):
        # Arrange
        attrs = {(None, "href"): "https://external.com/", (None, "rel"): "noopener"}

        # Act
        result = set_link_attributes(attrs)

        # Assert
        self.assertIn((None, "rel"), result)
        self.assertIn("noopener", result[(None, "rel")])
        self.assertIn("nofollow", result[(None, "rel")])

    # --- render_markdown ---
    def test_render_markdown_basic(self):
        # Arrange
        text = "# Title\nParagraph"

        # Act
        html = render_markdown(text)

        # Assert
        self.assertIn('id="title">Title</h1>', html)
        self.assertIn("<p>Paragraph</p>", html)

    def test_render_markdown_empty(self):
        # Arrange & Act
        html = render_markdown(None)

        # Assert
        self.assertEqual(html, "")

    def test_render_markdown_sanitizes_script(self):
        # Arrange
        text = "<script>alert('xss');</script>Test"

        # Act
        html = render_markdown(text)

        # Assert
        self.assertNotIn("<script>", html)
        self.assertIn("Test", html)

    def test_render_markdown_linkify(self):
        # Arrange
        text = "Visit https://google.com"

        # Act
        html = render_markdown(text)

        # Assert
        self.assertIn('href="https://google.com"', html)
        self.assertIn('rel="nofollow"', html)
