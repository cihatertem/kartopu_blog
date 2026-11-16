from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import TestCase


class SidebarTemplateSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

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

        self.assertIn("goal-widget__fill--45", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("style=", html)

    def test_sidebar_dividend_widget_renders_without_inline_style_or_progressbar(self):
        html = render_to_string(
            "includes/sidebar_dividend_widget.html",
            {
                "dividend_widget_snapshot": {
                    "year": 2026,
                    "currency": "USD",
                    "currency_symbol": "$",
                    "current_display": "3.245,80 $",
                    "previous_year": 2025,
                    "previous_display": "522,16 $",
                    "change_pct_display": "+%521,6",
                    "change_arrow": "↗",
                    "is_positive": True,
                    "snapshot_date_display": "16 Kasım 2026",
                }
            },
        )

        self.assertIn("Temettü Geliri", html)
        self.assertIn("2026 TOPLAM TEMETTÜ", html)
        self.assertIn("3.245,80 $", html)
        self.assertIn("(2025: 522,16 $)", html)
        self.assertIn("Geçen yıla göre", html)
        self.assertIn("+%521,6", html)
        self.assertIn("16 Kasım 2026 itibarıyla", html)
        self.assertIn("dividend-widget__badge--positive", html)
        self.assertNotIn("progressbar", html)
        self.assertNotIn("style=", html)

    def test_sidebar_dividend_widget_renders_negative_badge(self):
        html = render_to_string(
            "includes/sidebar_dividend_widget.html",
            {
                "dividend_widget_snapshot": {
                    "year": 2026,
                    "currency": "TRY",
                    "currency_symbol": "₺",
                    "current_display": "15.000,00 ₺",
                    "previous_year": 2025,
                    "previous_display": "19.967,52 ₺",
                    "change_pct_display": "-%24,9",
                    "change_arrow": "↘",
                    "is_positive": False,
                    "snapshot_date_display": "16 Kasım 2026",
                }
            },
        )

        self.assertIn("dividend-widget__badge--negative", html)
        self.assertIn("-%24,9", html)
        self.assertNotIn("style=", html)
