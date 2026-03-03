from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from blog.feeds import CategoryPostsFeed, LatestPostsFeed, _safe_cover_size
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

        # Inherited item methods
        self.assertEqual(feed.item_title(self.post_with_cover), "Post with Cover")
        self.assertIsNotNone(feed.item_enclosure_url(self.post_with_cover))

        # Test fallback description if category has no description
        empty_cat = Category.objects.create(name="Empty")
        self.assertEqual(
            feed.description(empty_cat), "Kartopu Blog'daki en yeni kategori yazıları."
        )
