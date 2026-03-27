from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category, Tag
from core.models import AboutPage, AboutPageImage, PageSEO, SiteSettings
from core.templatetags.seo_tags import _make_absolute, get_seo_data


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

    def test_make_absolute_url(self):
        self.assertEqual(_make_absolute(None), "")
        self.assertEqual(_make_absolute(""), "")
        self.assertEqual(
            _make_absolute("http://example.com/image.png"),
            "http://example.com/image.png",
        )
        self.assertEqual(
            _make_absolute("https://example.com/image.png"),
            "https://example.com/image.png",
        )
        self.assertEqual(
            _make_absolute("/media/image.png"), "https://kartopu.money/media/image.png"
        )
        self.assertEqual(
            _make_absolute("media/image.png"), "https://kartopu.money/media/image.png"
        )

    def test_default_seo(self):
        request = self.factory.get("/")
        seo = get_seo_data({"request": request})
        self.assertEqual(seo.get("title"), "Default Title")
        self.assertEqual(seo.get("description"), "Default Description")
        self.assertEqual(seo.get("type"), "website")

    def test_post_seo(self):
        request = self.factory.get(self.post.get_absolute_url())

        self.post.category = self.category
        dummy_image = SimpleUploadedFile(
            name="test_cover.png",
            content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            content_type="image/png",
        )
        self.post.cover_image = dummy_image
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
        self.assertTrue(
            seo.get("image").startswith("https://kartopu.money/media/blog/")
        )
        self.assertIn("cover_", seo.get("image"))

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
        dummy_image = SimpleUploadedFile(
            name="pageseo_test.png",
            content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            content_type="image/png",
        )
        PageSEO.objects.create(
            path=path,
            title="Contact SEO Title",
            description="Contact SEO Desc",
            image=dummy_image,
        )
        request = self.factory.get(path)
        seo = get_seo_data({"request": request})

        self.assertEqual(seo.get("title"), "Contact SEO Title")
        self.assertEqual(seo.get("description"), "Contact SEO Desc")
        self.assertTrue(seo.get("image").startswith("https://kartopu.money/media/seo/"))

    def test_about_page_seo(self):
        about = AboutPage.objects.create(
            title="About Us", meta_title="Meta About", meta_description="About Desc"
        )
        dummy_image = SimpleUploadedFile(
            name="about_test.png",
            content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            content_type="image/png",
        )
        AboutPageImage.objects.create(
            page=about,
            image=dummy_image,
            order=0,
        )
        request = self.factory.get("/about/")
        seo = get_seo_data({"request": request, "about_page": about})
        self.assertEqual(seo.get("title"), "Meta About")
        self.assertEqual(seo.get("description"), "About Desc")
        self.assertTrue(
            seo.get("image").startswith(
                "https://kartopu.money/media/core/about/images/"
            )
        )

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

    def test_pageseo_exception_logging(self):
        from unittest.mock import patch

        request = self.factory.get("/")

        with patch(
            "core.templatetags.seo_tags.PageSEO.objects.filter",
            side_effect=Exception("Database error"),
        ):
            with self.assertLogs("core.templatetags.seo_tags", level="ERROR") as cm:
                seo = get_seo_data({"request": request})

                self.assertTrue(
                    any(
                        "Error generating SEO data for path: /" in msg
                        for msg in cm.output
                    )
                )

                self.assertEqual(seo.get("title"), "Default Title")
                self.assertEqual(seo.get("description"), "Default Description")


class GetSeoDataIsolatedTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_seo_data_no_request(self):
        context = {}
        result = get_seo_data(context)
        self.assertEqual(result, {})

    @patch("core.templatetags.seo_tags.SiteSettings.get_settings")
    @patch("core.templatetags.seo_tags._update_seo_from_context")
    @patch("core.templatetags.seo_tags._apply_page_seo_override")
    @patch("core.templatetags.seo_tags.get_language")
    @patch("core.templatetags.seo_tags._make_absolute")
    def test_get_seo_data_with_mocked_helpers(
        self,
        mock_make_absolute,
        mock_get_language,
        mock_apply_override,
        mock_update_context,
        mock_get_settings,
    ):
        request = self.factory.get("/test-path/")
        context = {"request": request, "q": "search"}

        mock_settings = MagicMock()
        mock_settings.default_meta_title = "Mock Title"
        mock_settings.default_meta_description = "Mock Description"
        mock_settings.default_meta_image = None
        mock_get_settings.return_value = mock_settings

        mock_make_absolute.return_value = "https://example.com/mock-image.jpg"
        mock_get_language.return_value = "en_US"

        result = get_seo_data(context)

        self.assertEqual(result["title"], "Mock Title")
        self.assertEqual(result["description"], "Mock Description")
        self.assertEqual(result["image"], "https://example.com/mock-image.jpg")
        self.assertEqual(result["locale"], "en_US")
        self.assertEqual(result["canonical_url"], "http://testserver/test-path/")
        self.assertEqual(result["type"], "website")
        self.assertEqual(result["twitter_card"], "summary_large_image")

        mock_update_context.assert_called_once_with(result, context, "Kartopu Money")
        mock_apply_override.assert_called_once_with(result, request)

    @patch("core.templatetags.seo_tags.SiteSettings.get_settings")
    @patch("core.templatetags.seo_tags._apply_page_seo_override")
    def test_get_seo_data_template_integration(
        self, mock_apply_override, mock_get_settings
    ):
        mock_settings = MagicMock()
        mock_settings.default_meta_title = "Template Title"
        mock_settings.default_meta_description = "Template Desc"
        mock_settings.default_meta_image = None
        mock_get_settings.return_value = mock_settings

        request = self.factory.get("/")
        context = Context({"request": request})
        template = Template(
            "{% load seo_tags %}{% get_seo_data as seo_data %}{{ seo_data.title }}"
        )

        rendered = template.render(context)
        self.assertEqual(rendered, "Template Title")
