from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.models import (
    AboutPage,
    AboutPageImage,
    ContactMessage,
    PageSEO,
    SidebarWidget,
    SiteSettings,
)


class SiteSettingsTest(TestCase):
    def setUp(self):
        cache.clear()
        SiteSettings.objects.all().delete()

    def test_singleton(self):
        SiteSettings.objects.create()

        with self.assertRaises(ValidationError):
            settings = SiteSettings(is_comments_enabled=False)
            settings.full_clean()
            settings.save()

    def test_get_settings_creates_default(self):
        settings = SiteSettings.get_settings()
        self.assertIsNotNone(settings)
        self.assertTrue(settings.is_comments_enabled)
        self.assertTrue(settings.is_newsletter_enabled)
        self.assertTrue(settings.is_contact_enabled)

    def test_cache_update_on_save(self):
        settings = SiteSettings.get_settings()
        settings.is_comments_enabled = False
        settings.save()

        cached_settings = cache.get("site_settings")
        self.assertFalse(cached_settings.is_comments_enabled)

        settings_from_method = SiteSettings.get_settings()
        self.assertFalse(settings_from_method.is_comments_enabled)


class PageSEOTest(TestCase):
    def test_save_adds_slash_and_strips(self):
        seo = PageSEO(path=" contact/ ", title="Test SEO")
        seo.save()
        self.assertEqual(seo.path, "/contact/")
        self.assertEqual(str(seo), "/contact/")

    def test_save_preserves_slash(self):
        seo = PageSEO(path="/about/", title="About SEO")
        seo.save()
        self.assertEqual(seo.path, "/about/")


class ContactMessageTest(TestCase):
    def test_str_representation(self):
        msg = ContactMessage.objects.create(
            name="John", subject="Greeting", email="test@test.com", message="Hi"
        )
        self.assertEqual(str(msg), "John - Greeting")


class AboutPageTest(TestCase):
    def setUp(self):
        AboutPage.objects.all().delete()

    def test_singleton(self):
        AboutPage.objects.create(title="Title 1", content="Content 1")

        with self.assertRaises(ValidationError):
            page = AboutPage(title="Title 2", content="Content 2")
            page.full_clean()
            page.save()

    def test_str_representation(self):
        page = AboutPage.objects.create(title="About Me", content="Content")
        self.assertEqual(str(page), "About Me")


class AboutPageImageTest(TestCase):
    def test_str_representation(self):
        page = AboutPage.objects.create(title="About Me", content="Content")

        # Create a valid test image to avoid UnidentifiedImageError
        import io

        img_buffer = io.BytesIO()
        valid_img = Image.new("RGB", (100, 100), color="red")
        valid_img.save(img_buffer, format="JPEG")
        valid_image_content = img_buffer.getvalue()

        img = AboutPageImage.objects.create(
            page=page,
            image=SimpleUploadedFile(
                "test.jpg", valid_image_content, content_type="image/jpeg"
            ),
        )
        self.assertEqual(str(img), "About Me - Görsel")

    def test_rendition_property_no_image(self):
        page = AboutPage.objects.create(title="About Me", content="Content")
        img = AboutPageImage(page=page)
        self.assertIsNone(img.rendition)


class SidebarWidgetTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_str_representation(self):
        widget = SidebarWidget.objects.create(
            title="Sidebar", template_name="test.html"
        )
        self.assertEqual(str(widget), "Sidebar")

    def test_save_invalidates_cache(self):
        cache.set("sidebar_widgets", "test_cache")
        SidebarWidget.objects.create(title="Widget 1", template_name="1.html")
        self.assertIsNone(cache.get("sidebar_widgets"))

    def test_delete_invalidates_cache(self):
        widget = SidebarWidget.objects.create(title="Widget 1", template_name="1.html")
        cache.set("sidebar_widgets", "test_cache")
        widget.delete()
        self.assertIsNone(cache.get("sidebar_widgets"))
