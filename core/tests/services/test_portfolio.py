from datetime import date
from unittest.mock import MagicMock

from django.test import TestCase

from core.services.portfolio import (
    build_comparison_name,
    build_snapshot_name,
    format_comparison_label,
    format_snapshot_label,
    generate_unique_slug,
)


class PortfolioServicesTest(TestCase):
    def test_build_snapshot_name(self):
        name = build_snapshot_name("UserA", date(2023, 1, 1))
        self.assertEqual(name, "UserA - 2023-01-01")

        name_no_date = build_snapshot_name("UserB", None)
        self.assertEqual(name_no_date, "UserB")

    def test_format_snapshot_label(self):
        label1 = format_snapshot_label(
            slug="custom-slug", name=None, owner_label="User", snapshot_date=None
        )
        self.assertEqual(label1, "custom-slug")

        label2 = format_snapshot_label(
            slug=None, name="Custom Name", owner_label="User", snapshot_date=None
        )
        self.assertEqual(label2, "Custom Name")

        label3 = format_snapshot_label(
            slug=None, name=None, owner_label="User", snapshot_date=date(2023, 1, 1)
        )
        self.assertEqual(label3, "User - 2023-01-01")

    def test_build_comparison_name(self):
        base = MagicMock(name="Base")
        base.name = "Base Name"

        compare = MagicMock(name="Compare")
        compare.name = "Compare Name"

        self.assertEqual(
            build_comparison_name(base, compare), "Base Name → Compare Name"
        )

        base.name = None
        base.__str__.return_value = "BaseStr"
        compare.name = None
        compare.__str__.return_value = "CompareStr"

        self.assertEqual(build_comparison_name(base, compare), "BaseStr → CompareStr")

    def test_format_comparison_label(self):
        self.assertEqual(
            format_comparison_label(
                slug="comp-slug", name=None, base_snapshot="A", compare_snapshot="B"
            ),
            "comp-slug",
        )

        self.assertEqual(
            format_comparison_label(
                slug=None, name="Comp Name", base_snapshot="A", compare_snapshot="B"
            ),
            "Comp Name",
        )

        self.assertEqual(
            format_comparison_label(
                slug=None, name=None, base_snapshot="A", compare_snapshot="B"
            ),
            "A → B",
        )

    def test_generate_unique_slug(self):
        # We need a Django model to test generating slugs against its `.objects.filter()`
        from blog.models import Category

        slug1 = generate_unique_slug(Category, "My Special Name")
        self.assertTrue(slug1.startswith("my-special-name#"))

        slug2 = generate_unique_slug(Category, "My Special Name")
        self.assertNotEqual(slug1, slug2)

        # Test long names
        long_name = "a" * 300
        slug3 = generate_unique_slug(Category, long_name)
        self.assertLessEqual(len(slug3), 255)
