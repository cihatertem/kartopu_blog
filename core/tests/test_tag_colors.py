from unittest.mock import MagicMock

from django.test import TestCase

from core.tag_colors import TAG_COLOR_CLASSES, build_tag_items, get_tag_color_class


class TagColorsTest(TestCase):
    def test_get_tag_color_class(self):
        # Empty input should return the first class
        self.assertEqual(get_tag_color_class(""), TAG_COLOR_CLASSES[0])
        self.assertEqual(get_tag_color_class(None), TAG_COLOR_CLASSES[0])

        # Test deterministic output
        color1 = get_tag_color_class("python")
        color2 = get_tag_color_class("python")
        self.assertEqual(color1, color2)

        # Output should be one of the predefined classes
        self.assertIn(color1, TAG_COLOR_CLASSES)

    def test_build_tag_items(self):
        tag1 = MagicMock(name="Python", slug="python")
        tag2 = MagicMock(name="Django", slug="django")

        items = build_tag_items([tag1, tag2])

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], tag1.name)
        self.assertEqual(items[0]["slug"], tag1.slug)
        self.assertIn("color_class", items[0])

        self.assertEqual(items[1]["name"], tag2.name)
        self.assertEqual(items[1]["slug"], tag2.slug)
        self.assertIn("color_class", items[1])
