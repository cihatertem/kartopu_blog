from django.test import SimpleTestCase

from accounts.signals import _find_key_in_mapping, _find_value_by_path


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


class FindKeyInMappingTests(SimpleTestCase):
    def test_direct_match(self):
        data = {"target_key": "found_me", "other_key": "value"}
        self.assertEqual(_find_key_in_mapping(data, "target_key"), "found_me")

    def test_nested_match(self):
        data = {"other": "value", "nested": {"target_key": "found_nested"}}
        self.assertEqual(_find_key_in_mapping(data, "target_key"), "found_nested")

    def test_deeply_nested_match(self):
        data = {"level1": {"level2": {"level3": {"target_key": "deep_found"}}}}
        self.assertEqual(_find_key_in_mapping(data, "target_key"), "deep_found")

    def test_first_match_returned(self):
        data = {
            "first_dict": {"target_key": "first_match"},
            "second_dict": {"target_key": "second_match"},
        }
        # Dictionaries maintain insertion order in Python 3.7+
        self.assertEqual(_find_key_in_mapping(data, "target_key"), "first_match")

    def test_no_match(self):
        data = {"other_key": "value", "nested": {"another_key": "value"}}
        self.assertIsNone(_find_key_in_mapping(data, "target_key"))

    def test_non_string_value_ignored(self):
        # Even if the target_key matches, if the value is not a string, it keeps searching.
        data = {
            "first_nested": {"target_key": 123},
            "second_nested": {"target_key": ["not", "a", "string"]},
            "third_nested": {"target_key": "valid_string"},
        }
        self.assertEqual(_find_key_in_mapping(data, "target_key"), "valid_string")

    def test_non_string_value_returns_none_if_no_string_match(self):
        data = {
            "first_nested": {"target_key": 123},
            "second_nested": {"target_key": ["not", "a", "string"]},
        }
        self.assertIsNone(_find_key_in_mapping(data, "target_key"))

    def test_empty_mapping(self):
        self.assertIsNone(_find_key_in_mapping({}, "target_key"))

    def test_non_mapping_values_ignored(self):
        data = {"key1": "value", "key2": ["list", "item"], "target_key": 42}
        self.assertIsNone(_find_key_in_mapping(data, "target_key"))
