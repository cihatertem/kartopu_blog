from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from blog.feeds import (
    CategoryPostsFeed,
    LatestPostsFeed,
    _fallback_cover_name,
    _get_cover_name,
    _safe_cover_size,
)
from blog.models import BlogPost, Category

User = get_user_model()


class BlogFeedsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="feed_author@example.com", password="password"
        )
        self.category = Category.objects.create(
            name="Feed Category", description="A test category"
        )

        import io

        from PIL import Image

        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        file.seek(0)
        self.cover = SimpleUploadedFile(
            "cover.jpg", file.read(), content_type="image/jpeg"
        )

        self.post_with_cover = BlogPost.objects.create(
            title="Post with Cover",
            author=self.user,
            category=self.category,
            content="Content for cover post",
            excerpt="Short excerpt.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            cover_image=self.cover,
        )

        self.post_no_cover = BlogPost.objects.create(
            title="Post without Cover",
            author=self.user,
            category=self.category,
            content="Content for no cover post. " * 20,  # Long content
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        self.draft_post = BlogPost.objects.create(
            title="Draft Post",
            author=self.user,
            category=self.category,
            content="Draft",
            status=BlogPost.Status.DRAFT,
        )

    def test_safe_cover_size(self):
        # With valid field
        size = _safe_cover_size(self.post_with_cover.cover_image)
        self.assertIsNotNone(size)
        self.assertGreater(size, 0)

    def test_fallback_cover_name(self):
        # With cover
        name = _fallback_cover_name(self.post_with_cover)
        self.assertIsNotNone(name)

        # Without cover
        name = _fallback_cover_name(self.post_no_cover)
        self.assertIsNone(name)

        # No cover_image attribute
        class MissingAttr:
            pass

        self.assertIsNone(_fallback_cover_name(MissingAttr()))

    def test_get_cover_name(self):
        # With valid image processing
        self.assertIsNotNone(_get_cover_name(self.post_with_cover))

        # Test exception path handled by log_exceptions default_factory
        class BadItem:
            @property
            def cover_1200(self):
                raise Exception("Bad file")

            cover_image = MagicMock(name="fallback.jpg")

        bad_item = BadItem()
        # Fallback will return the mock's string repr or name depending on the mock configuration
        # but _fallback_cover_name grabs getattr(cover_image, 'name') which for a mock is its configured name or we can explicitly set it
        bad_item.cover_image.name = "fallback.jpg"

        self.assertEqual(_get_cover_name(bad_item), "fallback.jpg")

        # With invalid field (should return None safely due to log_exceptions)
        class BadImageField:
            @property
            def size(self):
                raise Exception("Storage error")

        bad_field = BadImageField()
        size_err = _safe_cover_size(bad_field)
        self.assertIsNone(size_err)

    def test_latest_posts_feed(self):
        feed = LatestPostsFeed()
        feed.request = self.factory.get("/")

        items = feed.items()
        self.assertEqual(len(items), 2)
        self.assertNotIn(self.draft_post, items)

        # Test item metadata for post_with_cover
        self.assertEqual(feed.item_title(self.post_with_cover), "Post with Cover")
        self.assertEqual(
            feed.item_description(self.post_with_cover), "<p>Short excerpt.</p>"
        )
        self.assertEqual(
            feed.item_link(self.post_with_cover),
            self.post_with_cover.get_absolute_url(),
        )
        self.assertEqual(
            feed.item_pubdate(self.post_with_cover), self.post_with_cover.published_at
        )

        # Test item metadata for post_no_cover (fallback to truncated content)
        desc_no_cover = feed.item_description(self.post_no_cover)
        self.assertIn("Content for no cover", desc_no_cover)

        # Enclosures
        self.assertIsNotNone(feed.item_enclosure_url(self.post_with_cover))
        self.assertTrue(
            str(feed.item_enclosure_url(self.post_with_cover)).startswith("http")
        )
        self.assertGreater(feed.item_enclosure_length(self.post_with_cover), 0)
        self.assertIn("image", feed.item_enclosure_mime_type(self.post_with_cover))

        # Missing cover
        self.assertIsNone(feed.item_enclosure_url(self.post_no_cover))
        self.assertIsNone(feed.item_enclosure_length(self.post_no_cover))
        self.assertIsNone(feed.item_enclosure_mime_type(self.post_no_cover))

    def test_item_enclosure_mime_type_missing_cover_name(self):
        feed = LatestPostsFeed()
        feed.request = self.factory.get("/")

        class BadMimeItem:
            cover_image = "exists"
            cover_rendition = None
            cover_1200 = MagicMock()
            cover_1200.name = None  # this makes _get_cover_name return None

        bad_item = BadMimeItem()
        self.assertEqual(feed.item_enclosure_mime_type(bad_item), "image/webp")

    def test_item_enclosure_url_without_request_and_safe_url(self):
        feed = LatestPostsFeed()
        # Ensure no request is set
        if hasattr(feed, "request"):
            delattr(feed, "request")

        class MockItem:
            cover_image = MagicMock()
            cover_rendition = None

        item = MockItem()

        with patch("blog.feeds.safe_file_url", return_value="/media/safe_url.jpg"):
            self.assertEqual(feed._get_item_cover_url(item), "/media/safe_url.jpg")

        with patch("blog.feeds.safe_file_url", return_value=None):
            self.assertIsNone(feed._get_item_cover_url(item))

    def test_category_posts_feed(self):
        feed = CategoryPostsFeed()
        feed.request = self.factory.get("/")

        # Test get_object
        obj = feed.get_object(feed.request, self.category.slug)
        self.assertEqual(obj, self.category)

        # Test basic info
        self.assertEqual(feed.title(obj), "Kartopu Blog - Feed Category Yazıları")
        self.assertEqual(feed.link(obj), obj.get_absolute_url())
        self.assertEqual(feed.description(obj), "A test category")

        # Items
        items = feed.items(obj)
        self.assertEqual(len(items), 2)
        self.assertNotIn(self.draft_post, items)

        # Inherited item methods for post_with_cover
        self.assertEqual(feed.item_title(self.post_with_cover), "Post with Cover")
        self.assertEqual(
            feed.item_description(self.post_with_cover), "<p>Short excerpt.</p>"
        )
        self.assertEqual(
            feed.item_link(self.post_with_cover),
            self.post_with_cover.get_absolute_url(),
        )
        self.assertEqual(
            feed.item_pubdate(self.post_with_cover), self.post_with_cover.published_at
        )

        # Inherited item methods for post_no_cover
        desc_no_cover = feed.item_description(self.post_no_cover)
        self.assertIn("Content for no cover", desc_no_cover)

        # Enclosures for post_with_cover
        self.assertIsNotNone(feed.item_enclosure_url(self.post_with_cover))
        self.assertTrue(
            str(feed.item_enclosure_url(self.post_with_cover)).startswith("http")
        )
        self.assertGreater(feed.item_enclosure_length(self.post_with_cover), 0)
        self.assertIn("image", feed.item_enclosure_mime_type(self.post_with_cover))

        # Enclosures for post_no_cover (missing cover)
        self.assertIsNone(feed.item_enclosure_url(self.post_no_cover))
        self.assertIsNone(feed.item_enclosure_length(self.post_no_cover))
        self.assertIsNone(feed.item_enclosure_mime_type(self.post_no_cover))

        # Test fallback description if category has no description
        empty_cat = Category.objects.create(name="Empty")
        self.assertEqual(
            feed.description(empty_cat), "Kartopu Blog'daki en yeni kategori yazıları."
        )

    def test_category_item_enclosure_mime_type_missing_cover_name(self):
        feed = CategoryPostsFeed()
        feed.request = self.factory.get("/")

        class BadMimeItem:
            cover_image = "exists"
            cover_rendition = None
            cover_1200 = MagicMock()
            cover_1200.name = None

        bad_item = BadMimeItem()
        self.assertEqual(feed.item_enclosure_mime_type(bad_item), "image/webp")

    def test_category_item_enclosure_url_without_request_and_safe_url(self):
        feed = CategoryPostsFeed()
        if hasattr(feed, "request"):
            delattr(feed, "request")

        class MockItem:
            cover_image = MagicMock()
            cover_rendition = None

        item = MockItem()

        with patch("blog.feeds.safe_file_url", return_value="/media/safe_url_cat.jpg"):
            self.assertEqual(feed._get_item_cover_url(item), "/media/safe_url_cat.jpg")

        with patch("blog.feeds.safe_file_url", return_value=None):
            self.assertIsNone(feed._get_item_cover_url(item))
