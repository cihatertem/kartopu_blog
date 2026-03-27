from django.test import TestCase
from django.utils.safestring import SafeString

from newsletter.admin import DirectEmailAdmin
from newsletter.models import DirectEmail


class DirectEmailAdminSecurityTests(TestCase):
    def test_rendered_body_preview_returns_safestring(self):
        """
        Verify that `rendered_body_preview` returns a SafeString to prevent XSS
        without wrapping the return value of `render_markdown` in `mark_safe`
        directly within the admin interface.
        """
        admin = DirectEmailAdmin(DirectEmail, None)

        obj = DirectEmail(
            subject="Test",
            to_email="test@example.com",
            body="**Bold text** and <script>alert('xss');</script>",
        )

        preview = admin.rendered_body_preview(obj)

        self.assertIsInstance(preview, SafeString)

        self.assertNotIn("<script>", preview)
        self.assertIn("<strong>Bold text</strong>", preview)
