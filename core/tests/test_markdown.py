from django.test import TestCase, override_settings

from core.markdown import render_markdown, set_link_attributes


class MarkdownTests(TestCase):
    def test_set_link_attributes_no_href(self):
        attrs = {(None, "title"): "Test"}

        result = set_link_attributes(attrs)

        self.assertEqual(result, attrs)

    def test_set_link_attributes_internal_relative_link(self):
        attrs = {(None, "href"): "/about/", (None, "rel"): "nofollow"}

        result = set_link_attributes(attrs)

        self.assertNotIn((None, "rel"), result)

    def test_set_link_attributes_internal_anchor_link(self):
        attrs = {(None, "href"): "#top"}

        result = set_link_attributes(attrs)

        self.assertNotIn((None, "rel"), result)

    @override_settings(SITE_BASE_URL="https://example.com")
    def test_set_link_attributes_internal_absolute_link(self):
        attrs = {(None, "href"): "https://example.com/blog/"}

        result = set_link_attributes(attrs)

        self.assertNotIn((None, "rel"), result)

    @override_settings(SITE_BASE_URL="https://example.com")
    def test_set_link_attributes_external_link(self):
        attrs = {(None, "href"): "https://external.com/page/"}

        result = set_link_attributes(attrs)

        self.assertIn((None, "rel"), result)
        self.assertEqual(result[(None, "rel")], "nofollow")

    def test_set_link_attributes_external_link_preserves_rel(self):
        attrs = {(None, "href"): "https://external.com/", (None, "rel"): "noopener"}

        result = set_link_attributes(attrs)

        self.assertIn((None, "rel"), result)
        self.assertIn("noopener", result[(None, "rel")])
        self.assertIn("nofollow", result[(None, "rel")])

    def test_render_markdown_basic(self):
        text = "# Title\nParagraph"

        html = render_markdown(text)

        self.assertIn('id="title">Title</h1>', html)
        self.assertIn("<p>Paragraph</p>", html)

    def test_render_markdown_empty(self):
        html = render_markdown(None)

        self.assertEqual(html, "")

    def test_render_markdown_sanitizes_script(self):
        text = "<script>alert('xss');</script>Test"

        html = render_markdown(text)

        self.assertNotIn("<script>", html)
        self.assertIn("Test", html)

    def test_render_markdown_linkify(self):
        text = "Visit https://google.com"

        html = render_markdown(text)

        self.assertIn('href="https://google.com"', html)
        self.assertIn('rel="nofollow"', html)
