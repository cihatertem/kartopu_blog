from django.contrib.admin.sites import site as default_site
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from core.admin import (
    AboutPageAdmin,
    AboutPageImageInline,
    ContactMessageAdmin,
    PageSEOAdmin,
    SidebarWidgetAdmin,
    SiteSettingsAdmin,
)
from core.models import (
    AboutPage,
    AboutPageImage,
    ContactMessage,
    PageSEO,
    SidebarWidget,
    SiteSettings,
)


class MockRequest:
    pass


User = get_user_model()


class AdminTests(TestCase):
    def setUp(self):
        self.site = default_site
        self.request = RequestFactory().get("/")
        self.user = User.objects.create_user(
            email="admin@test.com", password="password"
        )
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.request.user = self.user

    # --- SiteSettingsAdmin Tests ---
    def test_site_settings_has_add_permission_first_time(self):
        # Arrange
        SiteSettings.objects.all().delete()
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        # Act
        has_perm = admin.has_add_permission(self.request)

        # Assert
        self.assertTrue(has_perm)

    def test_site_settings_has_add_permission_already_exists(self):
        # Arrange
        SiteSettings.objects.create()
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        # Act
        has_perm = admin.has_add_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    def test_site_settings_has_delete_permission(self):
        # Arrange
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        # Act
        has_perm = admin.has_delete_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    # --- PageSEOAdmin Tests ---
    def test_page_seo_admin_registered(self):
        # Assert
        self.assertIn(PageSEO, self.site._registry)
        admin = self.site._registry[PageSEO]
        self.assertIsInstance(admin, PageSEOAdmin)

    # --- ContactMessageAdmin Tests ---
    def test_contact_message_mark_as_read(self):
        # Arrange
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_read=False
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        # Act
        admin.mark_as_read(self.request, queryset)

        # Assert
        self.assertTrue(ContactMessage.objects.first().is_read)

    def test_contact_message_mark_as_unread(self):
        # Arrange
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_read=True
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        # Act
        admin.mark_as_unread(self.request, queryset)

        # Assert
        self.assertFalse(ContactMessage.objects.first().is_read)

    def test_contact_message_mark_as_spam(self):
        # Arrange
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_spam=False
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        # Act
        admin.mark_as_spam(self.request, queryset)

        # Assert
        self.assertTrue(ContactMessage.objects.first().is_spam)

    def test_contact_message_mark_as_not_spam(self):
        # Arrange
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_spam=True
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        # Act
        admin.mark_as_not_spam(self.request, queryset)

        # Assert
        self.assertFalse(ContactMessage.objects.first().is_spam)

    # --- AboutPageAdmin Tests ---
    def test_about_page_has_add_permission_first_time(self):
        # Arrange
        AboutPage.objects.all().delete()
        admin = AboutPageAdmin(AboutPage, self.site)

        # Act
        has_perm = admin.has_add_permission(self.request)

        # Assert
        self.assertTrue(has_perm)

    def test_about_page_has_add_permission_already_exists(self):
        # Arrange
        AboutPage.objects.create(title="About", content="Content")
        admin = AboutPageAdmin(AboutPage, self.site)

        # Act
        has_perm = admin.has_add_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    def test_about_page_has_delete_permission(self):
        # Arrange
        admin = AboutPageAdmin(AboutPage, self.site)

        # Act
        has_perm = admin.has_delete_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    def test_about_page_public_link(self):
        # Arrange
        page = AboutPage.objects.create(title="About", content="Content")
        admin = AboutPageAdmin(AboutPage, self.site)

        # Act
        link = admin.public_link(page)

        # Assert
        self.assertIn("href='/hakkimizda/'", link)
        self.assertIn("Sayfayı Gör", link)

    # --- SidebarWidgetAdmin Tests ---
    def test_sidebar_widget_has_add_permission(self):
        # Arrange
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        has_perm = admin.has_add_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    def test_sidebar_widget_has_delete_permission_existing_template(self):
        # Arrange
        # Using a core built-in template that is guaranteed to exist.
        widget = SidebarWidget.objects.create(
            title="Test", template_name="includes/sidebar_popular_posts.html"
        )
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        has_perm = admin.has_delete_permission(self.request, obj=widget)

        # Assert
        # If template file exists, you can NOT delete it.
        self.assertFalse(has_perm)

    def test_sidebar_widget_has_delete_permission_missing_template(self):
        # Arrange
        widget = SidebarWidget.objects.create(
            title="Test", template_name="includes/does_not_exist.html"
        )
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        has_perm = admin.has_delete_permission(self.request, obj=widget)

        # Assert
        # If template file does not exist, you CAN delete it.
        self.assertTrue(has_perm)

    def test_sidebar_widget_has_delete_permission_no_obj(self):
        # Arrange
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        has_perm = admin.has_delete_permission(self.request)

        # Assert
        self.assertFalse(has_perm)

    def test_sidebar_widget_sync_widgets(self):
        # Arrange
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        admin.sync_widgets()

        # Assert
        # At least one built-in sidebar widget from the filesystem should be registered
        self.assertTrue(
            SidebarWidget.objects.filter(template_name__contains="sidebar_").exists()
        )

    def test_sidebar_widget_get_queryset_calls_sync(self):
        # Arrange
        SidebarWidget.objects.all().delete()
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        # Act
        qs = admin.get_queryset(self.request)

        # Assert
        self.assertTrue(qs.count() > 0)


class AboutPageImageInlineTests(TestCase):
    def setUp(self):
        self.site = default_site
        self.page = AboutPage.objects.create(title="About", content="Content")

    def test_thumb_no_pk(self):
        # Arrange
        inline = AboutPageImageInline(AboutPage, self.site)
        obj = AboutPageImage()

        # Act
        result = inline.thumb(obj)

        # Assert
        self.assertEqual(result, "—")

    def test_thumb_no_image(self):
        # Arrange
        inline = AboutPageImageInline(AboutPage, self.site)
        obj = AboutPageImage(page=self.page)
        obj.save()

        # Act
        result = inline.thumb(obj)

        # Assert
        self.assertEqual(result, "—")

    def test_thumb_with_image(self):
        # Arrange
        inline = AboutPageImageInline(AboutPage, self.site)

        # We need a fully valid image so that ImageKit resize generators don't fail when obj.save() is called
        import io

        from PIL import Image

        image_stream = io.BytesIO()
        image = Image.new("RGB", (100, 100), color="red")
        image.save(image_stream, format="JPEG")

        test_image = SimpleUploadedFile(
            name="test.jpg", content=image_stream.getvalue(), content_type="image/jpeg"
        )
        obj = AboutPageImage(page=self.page, image=test_image)
        obj.save()

        # Act
        result = inline.thumb(obj)

        # Assert
        self.assertIn("<img src='", result)
        self.assertIn("class='admin-thumb'", result)

        # Cleanup
        obj.image.delete(save=False)
