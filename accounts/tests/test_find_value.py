from django.test import SimpleTestCase

from accounts.signals import _find_value_by_path


class FindValueByPathTests(SimpleTestCase):
    def test_direct_key(self):
        data = {"picture": "http://example.com/a.jpg"}
        self.assertEqual(
            _find_value_by_path(data, "picture"), "http://example.com/a.jpg"
        )

    def test_dot_path(self):
        data = {"a": {"b": {"c": "http://example.com/b.jpg"}}}
        self.assertEqual(_find_value_by_path(data, "a.b.c"), "http://example.com/b.jpg")

    def test_recursive_fallback(self):
        data = {"x": {"y": {"picture": "http://example.com/c.jpg"}}}
        self.assertEqual(
            _find_value_by_path(data, "picture"), "http://example.com/c.jpg"
        )

    def test_invalid_data(self):
        self.assertIsNone(_find_value_by_path(None, "picture"))
        self.assertIsNone(_find_value_by_path({}, ""))

    def test_dot_path_not_found(self):
        data = {"a": {"b": "not a mapping"}}
        self.assertIsNone(_find_value_by_path(data, "a.b.c"))

    def test_dot_path_returns_none_if_not_str(self):
        data = {"a": {"b": {"c": 123}}}
        # Since it's not a string, it will fallback to recursive search
        # If recursive search also doesn't find it (as a string), it returns None
        self.assertIsNone(_find_value_by_path(data, "a.b.c"))

    def test_dot_path_complex(self):
        data = {"user": {"profile": {"avatar": "http://example.com/avatar.png"}}}
        self.assertEqual(
            _find_value_by_path(data, "user.profile.avatar"),
            "http://example.com/avatar.png",
        )

    def test_recursive_deep(self):
        data = {"level1": {"level2": {"level3": {"target": "found_me"}}}}
        self.assertEqual(_find_value_by_path(data, "target"), "found_me")

    def test_recursive_first_match(self):
        data = {"a": {"target": "first"}, "b": {"target": "second"}}
        # It should return the first one it finds in the dictionary iteration order
        self.assertEqual(_find_value_by_path(data, "target"), "first")
