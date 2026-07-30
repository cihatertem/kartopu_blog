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
        self.assertEqual(
            set(result[(None, "rel")].split()), {"nofollow", "noopener", "noreferrer"}
        )

    def test_set_link_attributes_external_link_preserves_rel(self):
        attrs = {(None, "href"): "https://external.com/", (None, "rel"): "noopener"}

        result = set_link_attributes(attrs)

        self.assertIn((None, "rel"), result)
        self.assertIn("noopener", result[(None, "rel")])
        self.assertIn("nofollow", result[(None, "rel")])
        self.assertIn("noreferrer", result[(None, "rel")])

    def test_render_markdown_basic(self):
        text = "# Title\nParagraph"

        html = render_markdown(text)

        self.assertIn('id="title">Title</h1>', html)
        self.assertIn("<p>Paragraph</p>", html)

    def test_render_markdown_empty(self):
        html = render_markdown(None)

        self.assertEqual(html, "")

    def test_render_markdown_empty_string(self):
        html = render_markdown("")

        self.assertEqual(html, "")

    def test_render_markdown_whitespace(self):
        html = render_markdown("   \n   ")

        self.assertEqual(html, "")

    def test_render_markdown_falsy_types(self):
        self.assertEqual(render_markdown(0), "")
        self.assertEqual(render_markdown(False), "")
        self.assertEqual(render_markdown([]), "")

    def test_render_markdown_only_stripped_tags(self):
        html = render_markdown("<script>malicious()</script>")

        self.assertEqual(html, "malicious()")

    def test_render_markdown_sanitizes_script(self):
        text = "<script>alert('xss');</script>Test"

        html = render_markdown(text)

        self.assertNotIn("<script>", html)
        self.assertIn("Test", html)

    def test_render_markdown_linkify(self):
        text = "Visit https://google.com"

        html = render_markdown(text)

        self.assertIn('href="https://google.com"', html)
        self.assertIn("nofollow", html)
        self.assertIn("noopener", html)
        self.assertIn("noreferrer", html)

    def test_render_markdown_strips_javascript_links(self):
        text = "[Click here](javascript:alert(1))"
        html = render_markdown(text)
        self.assertNotIn("javascript:", html)
        self.assertIn("<a>Click here</a>", html)

    def test_render_markdown_strips_data_links(self):
        text = "[Click here](data:text/html,alert(1))"
        html = render_markdown(text)
        self.assertNotIn("data:", html)
        self.assertIn("<a>Click here</a>", html)

    def test_render_markdown_strips_javascript_image_src(self):
        text = "![Alt text](javascript:alert(1))"
        html = render_markdown(text)
        self.assertNotIn("javascript:", html)
        self.assertIn('<img alt="Alt text">', html)

    def test_render_markdown_strips_javascript_in_styles(self):
        text = (
            '<p style="color:red; background-image: url(javascript:alert(1));">Red</p>'
        )
        html = render_markdown(text)
        self.assertNotIn("javascript:", html)
        self.assertIn('<p style="color:red;">Red</p>', html)

    def test_render_markdown_strips_javascript_in_data_attributes(self):
        text = '<section data-portfolio-allocation="javascript:alert(1)">9</section>'
        html = render_markdown(text)
        self.assertNotIn("javascript:", html)
        self.assertIn("<section>9</section>", html)
