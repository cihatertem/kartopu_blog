from django.test import SimpleTestCase

from blog.services import detect_content_dependencies


class DetectContentDependenciesTest(SimpleTestCase):
    def test_detect_content_dependencies(self):
        cases = [
            ("", []),
            ("No tags here", []),
            ("{{ unknown_tag:1 }}", []),
            ("{{ portfolio_summary:1 }}", ["portfolio"]),
            ("{{ cashflow_summary:1 }}", ["cashflow"]),
            ("{{ savings_rate_summary:1 }}", ["salary_savings"]),
            ("{{ dividend_summary:1 }}", ["dividend"]),
            (
                "{{ portfolio_summary:1 }} and {{ cashflow_summary:1 }}",
                ["portfolio", "cashflow"],
            ),
            (
                "{{ portfolio_charts:2 }} and {{ savings_rate_charts:3 }}",
                ["portfolio", "salary_savings"],
            ),
            ("{{ invalid_tag:1 }} and {{ dividend_summary:1 }}", ["dividend"]),
        ]

        for content, expected in cases:
            with self.subTest(content=content):
                # Order doesn't matter for the assertion, but function appends in dictionary order
                # We can use assertCountEqual for a robust check
                self.assertCountEqual(detect_content_dependencies(content), expected)
