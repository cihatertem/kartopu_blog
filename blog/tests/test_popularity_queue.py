from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from blog.cache_keys import BLOG_POPULARITY_DIRTY_KEY
from blog.popularity_queue import drain_popularity_dirty


class PopularityQueueTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("blog.popularity_queue._get_redis_client")
    def test_drain_popularity_dirty_with_redis(self, mock_get_redis_client):
        # Redis client ve pipeline mock
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe

        # Pipeline execute() çağrısı smembers() sonucunu ve delete() sonucunu döndürür.
        # smembers genellikle bytes döndürür.
        mock_pipe.execute.return_value = ([b"post1", b"post2"], None)

        mock_get_redis_client.return_value = mock_client

        result = drain_popularity_dirty()

        self.assertEqual(result, {"post1", "post2"})
        mock_pipe.smembers.assert_called_once_with(BLOG_POPULARITY_DIRTY_KEY)
        mock_pipe.delete.assert_called_once_with(BLOG_POPULARITY_DIRTY_KEY)
        mock_pipe.execute.assert_called_once()

    @patch("blog.popularity_queue._get_redis_client")
    def test_drain_popularity_dirty_without_redis(self, mock_get_redis_client):
        # Redis client dönmezse Django cache kullanılmalı
        mock_get_redis_client.return_value = None

        # Cache'i dolduralım
        cache.set(BLOG_POPULARITY_DIRTY_KEY, {"post3", "post4"}, None)

        result = drain_popularity_dirty()

        self.assertEqual(result, {"post3", "post4"})
        self.assertIsNone(cache.get(BLOG_POPULARITY_DIRTY_KEY))

    @patch("blog.popularity_queue._get_redis_client")
    def test_drain_popularity_dirty_empty(self, mock_get_redis_client):
        mock_get_redis_client.return_value = None

        # Cache boşken
        result = drain_popularity_dirty()

        self.assertEqual(result, set())
