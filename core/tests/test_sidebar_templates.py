from django.template.loader import render_to_string
from django.test import TestCase


class SidebarTemplateSecurityTests(TestCase):
    def test_sidebar_tags_avoids_inline_style(self):
        html = render_to_string(
            "includes/sidebar_tags.html",
            {
                "nav_tags": [
                    {
                        "name": "Django",
                        "slug": "django",
                        "color_class": "tag-color-1",
                        "cloud_size_class": "tag-cloud__item--size-3",
                    }
                ],
                "active_tag_slug": "",
            },
        )

        self.assertIn("tag-cloud__item--size-3", html)
        self.assertNotIn("style=", html)

    def test_sidebar_goal_widget_avoids_inline_style(self):
        html = render_to_string(
            "includes/sidebar_goal_widget.html",
            {
                "goal_widget_snapshot": {
                    "name": "F.I.R.E",
                    "target_display": "1.000.000 ₺",
                    "current_display": "450.000 ₺",
                    "remaining_pct": {"value": 45, "display": 55},
                }
            },
        )

        self.assertIn("<svg", html)
        self.assertIn('width="45"', html)
        self.assertNotIn("style=", html)
