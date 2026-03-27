from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.services.portfolio import (
    _build_slug_base,
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

        name_empty_owner = build_snapshot_name("", date(2023, 1, 1))
        self.assertEqual(name_empty_owner, " - 2023-01-01")

        name_empty_no_date = build_snapshot_name("", None)
        self.assertEqual(name_empty_no_date, "")

        name_special = build_snapshot_name("User C & Co.", date(2023, 1, 1))
        self.assertEqual(name_special, "User C & Co. - 2023-01-01")

        long_name = "A" * 500
        name_long = build_snapshot_name(long_name, date(2023, 1, 1))
        self.assertEqual(name_long, f"{long_name} - 2023-01-01")

        name_unicode = build_snapshot_name("Täst Üser 🚀", date(2023, 1, 1))
        self.assertEqual(name_unicode, "Täst Üser 🚀 - 2023-01-01")

        name_numeric = build_snapshot_name("12345", date(2023, 1, 1))
        self.assertEqual(name_numeric, "12345 - 2023-01-01")

        from datetime import datetime

        dt = datetime(2023, 1, 1, 15, 30)
        name_datetime = build_snapshot_name("UserD", dt)
        self.assertEqual(name_datetime, "UserD - 2023-01-01 15:30:00")

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

        label4 = format_snapshot_label(
            slug="", name="", owner_label="User", snapshot_date=date(2023, 1, 1)
        )
        self.assertEqual(label4, "User - 2023-01-01")

        label5 = format_snapshot_label(
            slug=None, name=None, owner_label="User", snapshot_date=None
        )
        self.assertEqual(label5, "User")

        label6 = format_snapshot_label(
            slug="slug-only", name=None, owner_label="User", snapshot_date=None
        )
        self.assertEqual(label6, "slug-only")

        label7 = format_snapshot_label(
            slug=None, name="name-only", owner_label="User", snapshot_date=None
        )
        self.assertEqual(label7, "name-only")

        label8 = format_snapshot_label(
            slug="slug-has-priority",
            name="name-ignored",
            owner_label="User",
            snapshot_date=None,
        )
        self.assertEqual(label8, "slug-has-priority")

        label9 = format_snapshot_label(
            slug="",
            name="name-only-with-empty-slug",
            owner_label="User",
            snapshot_date=None,
        )
        self.assertEqual(label9, "name-only-with-empty-slug")

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

        base.name = None
        base.__str__.return_value = ""
        compare.name = "Compare Name"

        self.assertEqual(build_comparison_name(base, compare), "Compare Name")

        base.name = "Base Name"
        compare.name = None
        compare.__str__.return_value = ""

        self.assertEqual(build_comparison_name(base, compare), "Base Name")

        self.assertEqual(build_comparison_name(None, None), "None → None")

        class SnapshotWithoutNameAttr:
            def __str__(self):
                return "SnapshotStr"

        base_no_attr = SnapshotWithoutNameAttr()
        compare_no_attr = SnapshotWithoutNameAttr()
        self.assertEqual(
            build_comparison_name(base_no_attr, compare_no_attr),
            "SnapshotStr → SnapshotStr",
        )
        base.name = ""
        base.__str__.return_value = "BaseStrFallback"
        compare.name = ""
        compare.__str__.return_value = "CompareStrFallback"
        self.assertEqual(
            build_comparison_name(base, compare), "BaseStrFallback → CompareStrFallback"
        )

        base.name = "  "
        base.__str__.return_value = "BaseStrFallback"
        compare.name = "  "
        compare.__str__.return_value = "CompareStrFallback"
        self.assertEqual(build_comparison_name(base, compare), "   →   ")

        class MockSnapshot:
            name = None

            def __str__(self):
                return "None"

        self.assertEqual(
            build_comparison_name(MockSnapshot(), MockSnapshot()), "None → None"
        )

        class EmptySnapshot:
            def __str__(self):
                return ""

        empty_base = EmptySnapshot()
        empty_compare = EmptySnapshot()
        self.assertEqual(build_comparison_name(empty_base, empty_compare), "")

        class FalsySnapshotWithEmptyName(EmptySnapshot):
            name = ""

        falsy_base_name = FalsySnapshotWithEmptyName()
        falsy_compare_name = FalsySnapshotWithEmptyName()
        self.assertEqual(build_comparison_name(falsy_base_name, falsy_compare_name), "")

        class FalsySnapshot:
            def __bool__(self):
                return False

            def __str__(self):
                return "FalsyStr"

        falsy_base = FalsySnapshot()
        falsy_compare = FalsySnapshot()
        self.assertEqual(
            build_comparison_name(falsy_base, falsy_compare), "FalsyStr → FalsyStr"
        )

    def test_format_comparison_label(self):
        base = MagicMock()
        base.__str__.return_value = "BaseStr"
        compare = MagicMock()
        compare.__str__.return_value = "CompareStr"
        self.assertEqual(
            format_comparison_label(
                slug="comp-slug",
                name="Comp Name",
                base_snapshot=base,
                compare_snapshot=compare,
            ),
            "comp-slug",
        )

        self.assertEqual(
            format_comparison_label(
                slug="", name="Comp Name", base_snapshot=base, compare_snapshot=compare
            ),
            "Comp Name",
        )

        self.assertEqual(
            format_comparison_label(
                slug=None,
                name="Comp Name",
                base_snapshot=base,
                compare_snapshot=compare,
            ),
            "Comp Name",
        )

        self.assertEqual(
            format_comparison_label(
                slug="", name="", base_snapshot=base, compare_snapshot=compare
            ),
            "BaseStr → CompareStr",
        )

        class SnapshotWithStr:
            def __init__(self, val):
                self.val = val

            def __str__(self):
                return self.val

        base_val = SnapshotWithStr("BaseVal")
        compare_val = SnapshotWithStr("CompareVal")
        self.assertEqual(
            format_comparison_label(
                slug=None,
                name=None,
                base_snapshot=base_val,
                compare_snapshot=compare_val,
            ),
            "BaseVal → CompareVal",
        )

        self.assertEqual(
            format_comparison_label(
                slug=None,
                name=None,
                base_snapshot=None,
                compare_snapshot=None,
            ),
            "None → None",
        )

        self.assertEqual(
            format_comparison_label(
                slug=None, name=None, base_snapshot=base, compare_snapshot=compare
            ),
            "BaseStr → CompareStr",
        )

    def test_generate_unique_slug(self):
        from blog.models import Category

        slug1 = generate_unique_slug(Category, "My Special Name")
        self.assertTrue(slug1.startswith("my-special-name#"))

        slug2 = generate_unique_slug(Category, "My Special Name")
        self.assertNotEqual(slug1, slug2)

        long_name = "a" * 300
        slug3 = generate_unique_slug(Category, long_name)
        self.assertLessEqual(len(slug3), 255)

    @patch("core.services.portfolio.secrets.choice")
    def test_generate_unique_slug_collision(self, mock_choice):
        from blog.models import Category

        mock_choice.side_effect = ["a"] * 6 + ["b"] * 6

        mock_qs = MagicMock()
        mock_qs.exists.side_effect = [True, False]
        mock_filter = MagicMock(return_value=mock_qs)

        with patch.object(Category.objects, "filter", mock_filter):
            slug = generate_unique_slug(Category, "Test Collision")

        self.assertEqual(slug, "test-collision#bbbbbb")
        self.assertEqual(mock_qs.exists.call_count, 2)

    @patch("core.services.portfolio.secrets.choice")
    def test_generate_unique_slug_no_mocks(self, mock_choice):
        from blog.models import Category

        Category.objects.all().delete()

        mock_choice.side_effect = ["a"] * 6 + ["a"] * 6 + ["b"] * 6

        name = "Actual DB Test"
        slug1 = generate_unique_slug(Category, name)
        Category.objects.create(name=name, slug=slug1)

        slug2 = generate_unique_slug(Category, name)

        self.assertEqual(slug1, "actual-db-test#aaaaaa")
        self.assertEqual(slug2, "actual-db-test#bbbbbb")
        self.assertNotEqual(slug1, slug2)

    def test__build_slug_base_empty_name(self):
        base = _build_slug_base("", max_length=255)
        self.assertEqual(base, "snapshot")

        base_unslugifiable = _build_slug_base("!!!", max_length=255)
        self.assertEqual(base_unslugifiable, "snapshot")

    def test__build_slug_base_short_max_length(self):
        base = _build_slug_base("my-name", max_length=6)
        self.assertEqual(base, "my-name")

        base_edge = _build_slug_base("my-name", max_length=7)
        self.assertEqual(base_edge, "my-name")

        base_trunc = _build_slug_base("my-name", max_length=8)
        self.assertEqual(base_trunc, "m")

        base_zero = _build_slug_base("my-name", max_length=0)
        self.assertEqual(base_zero, "my-name")

        base_negative = _build_slug_base("my-name", max_length=-5)
        self.assertEqual(base_negative, "my-name")

        base_empty_trunc = _build_slug_base("", max_length=8)
        self.assertEqual(base_empty_trunc, "s")

        base_empty_edge = _build_slug_base("", max_length=7)
        self.assertEqual(base_empty_edge, "snapshot")
