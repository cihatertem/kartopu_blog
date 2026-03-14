from django.test import TestCase
from django.utils import timezone

from blog.models import BlogPost, Category, Tag
from core.sitemaps import (
    BlogCategorySitemap,
    BlogPostSitemap,
    BlogTagSitemap,
    StaticViewSitemap,
)


class SitemapsTest(TestCase):
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

    def test_blog_tag_sitemap(self):
        tag = Tag.objects.create(name="Python", slug="python")

        sitemap = BlogTagSitemap()
        items = sitemap.items()

        self.assertIn(tag, items)
        self.assertEqual(sitemap.lastmod(tag), tag.updated_at)
