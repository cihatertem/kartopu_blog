from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from core.models import (
    AboutPage,
    AboutPageImage,
    ContactMessage,
    PageSEO,
    SidebarWidget,
    SiteSettings,
    about_image_upload_path,
    site_settings_og_image_upload_path,
)


class SiteSettingsOgImageUploadPathTest(SimpleTestCase):
    @patch("django.utils.timezone.now")
    def test_valid_filename(self, mock_now):
        mock_now.return_value = datetime(
            2023, 10, 25, 12, 30, 45, tzinfo=ZoneInfo("UTC")
        )
        instance = None
        result = site_settings_og_image_upload_path(instance, "image.png")
        self.assertEqual(result, "seo/og_image_20231025123045.png")

    @patch("django.utils.timezone.now")
    def test_uppercase_extension(self, mock_now):
        mock_now.return_value = datetime(
            2023, 10, 25, 12, 30, 45, tzinfo=ZoneInfo("UTC")
        )
        instance = None
        result = site_settings_og_image_upload_path(instance, "IMAGE.JPG")
        self.assertEqual(result, "seo/og_image_20231025123045.jpg")

    @patch("django.utils.timezone.now")
    def test_filename_with_multiple_dots(self, mock_now):
        mock_now.return_value = datetime(
            2023, 10, 25, 12, 30, 45, tzinfo=ZoneInfo("UTC")
        )
        instance = None
        result = site_settings_og_image_upload_path(instance, "my.cool.image.webp")
        self.assertEqual(result, "seo/og_image_20231025123045.webp")


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


class AboutImageUploadPathTest(SimpleTestCase):
    @patch("django.utils.timezone.now")
    def test_standard_filename(self, mock_now):
        from datetime import timezone as dt_timezone

        mock_now.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)

        result = about_image_upload_path(None, "test.jpg")

        self.assertEqual(result, "core/about/images/test_20230101120000.jpg")

    @patch("django.utils.timezone.now")
    def test_special_characters_filename(self, mock_now):
        from datetime import timezone as dt_timezone

        mock_now.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)

        result = about_image_upload_path(None, "My Awesome Photo!.PNG")

        self.assertEqual(
            result, "core/about/images/my-awesome-photo_20230101120000.png"
        )


class AboutPageImageTest(TestCase):
    def test_str_representation(self):
        page = AboutPage.objects.create(title="About Me", content="Content")

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

    def test_rendition_property_with_image(self):
        page = AboutPage.objects.create(title="About Me", content="Content")

        import io

        img_buffer = io.BytesIO()
        # Use a larger image to ensure it's resized to 1200
        valid_img = Image.new("RGB", (2000, 1600), color="red")
        valid_img.save(img_buffer, format="JPEG")
        valid_image_content = img_buffer.getvalue()

        img = AboutPageImage.objects.create(
            page=page,
            image=SimpleUploadedFile(
                "test.jpg", valid_image_content, content_type="image/jpeg"
            ),
        )

        rendition = img.rendition
        self.assertIsNotNone(rendition)
        self.assertEqual(rendition["width"], 1200)
        self.assertEqual(rendition["height"], 960)  # 1600 * (1200/2000) = 960
        self.assertIn("src", rendition)
        self.assertIn("srcset", rendition)


class SidebarWidgetTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_str_representation(self):
        widget = SidebarWidget.objects.create(
            title="Sidebar", template_name="test.html"
        )
        self.assertEqual(str(widget), "Sidebar")
