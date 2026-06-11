from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from blog.cache_keys import SITEMAP_BLOG_POSTS_KEY, SITEMAP_CATEGORIES_KEY
from blog.models import BlogPost, Category
from core.sitemaps import (
    BlogCategorySitemap,
    BlogPostSitemap,
    StaticViewSitemap,
)


class SitemapsTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_static_view_sitemap(self):
        sitemap = StaticViewSitemap()
        items = sitemap.items()
        self.assertIn("core:home", items)
        self.assertIn("core:about", items)
        self.assertIn("core:contact", items)

        # Test location resolving
        self.assertEqual(sitemap.location("core:home"), "/")
        self.assertEqual(sitemap.location("core:about"), "/hakkimizda/")
        self.assertEqual(sitemap.location("core:contact"), "/iletisim/")

    def test_blog_post_sitemap(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="test@example.com")
        category = Category.objects.create(name="Tech", slug="tech")
        post1 = BlogPost.objects.create(
            author=user,
            title="Post 1",
            slug="post-1",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            category=category,
        )
        post2 = BlogPost.objects.create(
            author=user,
            title="Post 2",
            slug="post-2",
            status=BlogPost.Status.DRAFT,
            category=category,
        )

        sitemap = BlogPostSitemap()
        items = sitemap.items()

        self.assertIn(post1, items)
        self.assertNotIn(post2, items)

        self.assertEqual(sitemap.lastmod(post1), post1.updated_at or post1.published_at)

    def test_blog_category_sitemap(self):
        category = Category.objects.create(name="Tech", slug="tech")

        sitemap = BlogCategorySitemap()
        items = sitemap.items()

        self.assertIn(category, items)
        self.assertEqual(sitemap.lastmod(category), category.updated_at)

    def test_blog_post_sitemap_items_are_cached(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create(email="cache@example.com")
        category = Category.objects.create(name="Cache", slug="cache")
        BlogPost.objects.create(
            author=user,
            title="Cached Post",
            slug="cached-post",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            category=category,
        )

        sitemap = BlogPostSitemap()

        self.assertIsNone(cache.get(SITEMAP_BLOG_POSTS_KEY))

        # First call populates the cache with one query.
        with self.assertNumQueries(1):
            items = sitemap.items()
        self.assertEqual(len(items), 1)
        self.assertIsNotNone(cache.get(SITEMAP_BLOG_POSTS_KEY))

        # Second call is served from cache without touching the DB.
        with self.assertNumQueries(0):
            cached_items = sitemap.items()
        self.assertEqual(len(cached_items), 1)

    def test_blog_category_sitemap_items_are_cached(self):
        Category.objects.create(name="Cache", slug="cache")

        sitemap = BlogCategorySitemap()

        self.assertIsNone(cache.get(SITEMAP_CATEGORIES_KEY))

        with self.assertNumQueries(1):
            sitemap.items()
        self.assertIsNotNone(cache.get(SITEMAP_CATEGORIES_KEY))

        with self.assertNumQueries(0):
            sitemap.items()
