from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category, Tag
from core.models import AboutPage, PageSEO, SiteSettings
from core.templatetags.seo_tags import get_seo_data


@override_settings(SITE_BASE_URL="https://kartopu.money", SECURE_SSL_REDIRECT=False)
class SEOTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )

        self.site_settings, _ = SiteSettings.objects.get_or_create(
            defaults={
                "default_meta_title": "Default Title",
                "default_meta_description": "Default Description",
            }
        )
        self.site_settings.default_meta_title = "Default Title"
        self.site_settings.default_meta_description = "Default Description"
        self.site_settings.save()

        self.category = Category.objects.create(
            name="Test Category", slug="test-category", description="Category Desc"
        )
        self.tag = Tag.objects.create(name="Test Tag", slug="test-tag")
        self.post = BlogPost.objects.create(
            author=self.user,
            title="Test Post",
            slug="test-post",
            content="Content",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            meta_description="Post Meta Desc",
        )
        self.post.tags.add(self.tag)

    def test_default_seo(self):
        # Our home view normally triggers get_seo_data with empty context or specific ones
        # But we can test the tag directly
        request = self.factory.get("/")
        seo = get_seo_data({"request": request})
        self.assertEqual(seo.get("title"), "Default Title")
        self.assertEqual(seo.get("description"), "Default Description")
        self.assertEqual(seo.get("type"), "website")

    def test_post_seo(self):
        request = self.factory.get(self.post.get_absolute_url())

        # Ensure category is correctly assigned to post and fetched
        self.post.category = self.category
        self.post.save()
        post_with_cat = (
            BlogPost.objects.select_related("category", "author")
            .prefetch_related("tags")
            .get(pk=self.post.pk)
        )

        seo = get_seo_data({"request": request, "post": post_with_cat})
        self.assertEqual(seo.get("title"), post_with_cat.effective_meta_title)
        self.assertEqual(seo.get("description"), "Post Meta Desc")
        self.assertEqual(seo.get("type"), "article")
        self.assertEqual(seo.get("article_section"), "Test Category")
        self.assertIn("Test Tag", seo.get("article_tags", []))

    def test_category_seo(self):
        request = self.factory.get(self.category.get_absolute_url())
        seo = get_seo_data(
            {
                "request": request,
                "category": self.category,
                "active_category_slug": self.category.slug,
            }
        )
        self.assertIn("Test Category", seo.get("title"))
        self.assertEqual(seo.get("description"), "Category Desc")

    def test_tag_seo(self):
        request = self.factory.get(self.tag.get_absolute_url())
        seo = get_seo_data(
            {
                "request": request,
                "tag": self.tag,
                "active_tag_slug": self.tag.slug,
            }
        )
        self.assertIn("#Test Tag", seo.get("title"))

    def test_pageseo_override(self):
        path = reverse("core:contact")
        PageSEO.objects.create(
            path=path, title="Contact SEO Title", description="Contact SEO Desc"
        )
        request = self.factory.get(path)
        seo = get_seo_data({"request": request})

        self.assertEqual(seo.get("title"), "Contact SEO Title")
        self.assertEqual(seo.get("description"), "Contact SEO Desc")

    def test_about_page_seo(self):
        about = AboutPage.objects.create(
            title="About Us", meta_title="Meta About", meta_description="About Desc"
        )
        request = self.factory.get("/about/")
        seo = get_seo_data({"request": request, "about_page": about})
        self.assertEqual(seo.get("title"), "Meta About")
        self.assertEqual(seo.get("description"), "About Desc")

    def test_archive_seo(self):
        request = self.factory.get("/archive/2023/1/")
        seo = get_seo_data(
            {
                "request": request,
                "archive_month": "Ocak 2023",
                "active_archive_key": "2023-01",
            }
        )
        self.assertIn("Ocak 2023 Arşivi", seo.get("title"))

    def test_search_seo(self):
        request = self.factory.get("/search/?q=finance")
        seo = get_seo_data({"request": request, "q": "finance"})
        self.assertIn("'finance' Arama Sonuçları", seo.get("title"))

    def test_empty_request(self):
        seo = get_seo_data({})
        self.assertEqual(seo, {})

    def test_pageseo_exception_logging(self):
        from unittest.mock import patch

        request = self.factory.get("/")

        with patch(
            "core.templatetags.seo_tags.PageSEO.objects.filter",
            side_effect=Exception("Database error"),
        ):
            with self.assertLogs("core.templatetags.seo_tags", level="ERROR") as cm:
                seo = get_seo_data({"request": request})

                # Check that the exception was logged
                self.assertTrue(
                    any(
                        "Error generating SEO data for path: /" in msg
                        for msg in cm.output
                    )
                )

                # Check that the default SEO data is still returned
                self.assertEqual(seo.get("title"), "Default Title")
                self.assertEqual(seo.get("description"), "Default Description")
