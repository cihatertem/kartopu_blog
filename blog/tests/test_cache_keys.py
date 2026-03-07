from django.test import SimpleTestCase

from blog.cache_keys import (
    CACHE_KEY_SAVINGS_RATE,
    NAV_ARCHIVES_KEY,
    NAV_CATEGORIES_KEY,
    NAV_KEYS,
    NAV_POPULAR_POSTS_KEY,
    NAV_PORTFOLIO_POSTS_KEY,
    NAV_RECENT_POSTS_KEY,
    NAV_TAGS_KEY,
)


class CacheKeysTests(SimpleTestCase):
    """
    Test suite for blog.cache_keys constants.
    """

    def test_nav_keys_contents(self):
        """
        Verify that NAV_KEYS contains all the specific navigation keys exactly.
        """
        expected_keys = [
            NAV_CATEGORIES_KEY,
            NAV_TAGS_KEY,
            NAV_ARCHIVES_KEY,
            NAV_RECENT_POSTS_KEY,
            NAV_POPULAR_POSTS_KEY,
            NAV_PORTFOLIO_POSTS_KEY,
        ]

        # Verify the list elements match exactly
        self.assertEqual(NAV_KEYS, expected_keys)

    def test_nav_keys_are_unique(self):
        """
        Verify that all keys in NAV_KEYS are unique.
        """
        self.assertEqual(len(NAV_KEYS), len(set(NAV_KEYS)))

    def test_nav_keys_are_strings(self):
        """
        Verify that all keys in NAV_KEYS are strings.
        """
        for key in NAV_KEYS:
            self.assertIsInstance(key, str)
            self.assertTrue(len(key) > 0)

    def test_cache_key_savings_rate(self):
        """
        Verify the value of CACHE_KEY_SAVINGS_RATE constant.
        """
        self.assertEqual(CACHE_KEY_SAVINGS_RATE, "savings_rate")
