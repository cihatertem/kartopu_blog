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

    def test_site_settings_has_add_permission_first_time(self):
        SiteSettings.objects.all().delete()
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        has_perm = admin.has_add_permission(self.request)

        self.assertTrue(has_perm)

    def test_site_settings_has_add_permission_already_exists(self):
        SiteSettings.objects.create()
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        has_perm = admin.has_add_permission(self.request)

        self.assertFalse(has_perm)

    def test_site_settings_has_delete_permission(self):
        admin = SiteSettingsAdmin(SiteSettings, self.site)

        has_perm = admin.has_delete_permission(self.request)

        self.assertFalse(has_perm)

    def test_page_seo_admin_registered(self):
        # Assert
        self.assertIn(PageSEO, self.site._registry)
        admin = self.site._registry[PageSEO]
        self.assertIsInstance(admin, PageSEOAdmin)

    def test_contact_message_mark_as_read(self):
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_read=False
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        admin.mark_as_read(self.request, queryset)

        self.assertTrue(ContactMessage.objects.first().is_read)

    def test_contact_message_mark_as_unread(self):
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_read=True
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        admin.mark_as_unread(self.request, queryset)

        self.assertFalse(ContactMessage.objects.first().is_read)

    def test_contact_message_mark_as_spam(self):
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_spam=False
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        admin.mark_as_spam(self.request, queryset)

        self.assertTrue(ContactMessage.objects.first().is_spam)

    def test_contact_message_mark_as_not_spam(self):
        ContactMessage.objects.create(
            name="A", subject="S", email="a@a.com", message="M", is_spam=True
        )
        admin = ContactMessageAdmin(ContactMessage, self.site)
        queryset = ContactMessage.objects.all()

        admin.mark_as_not_spam(self.request, queryset)

        self.assertFalse(ContactMessage.objects.first().is_spam)

    def test_about_page_has_add_permission_first_time(self):
        AboutPage.objects.all().delete()
        admin = AboutPageAdmin(AboutPage, self.site)

        has_perm = admin.has_add_permission(self.request)

        self.assertTrue(has_perm)

    def test_about_page_has_add_permission_already_exists(self):
        AboutPage.objects.create(title="About", content="Content")
        admin = AboutPageAdmin(AboutPage, self.site)

        has_perm = admin.has_add_permission(self.request)

        self.assertFalse(has_perm)

    def test_about_page_has_delete_permission(self):
        admin = AboutPageAdmin(AboutPage, self.site)

        has_perm = admin.has_delete_permission(self.request)

        self.assertFalse(has_perm)

    def test_about_page_public_link(self):
        page = AboutPage.objects.create(title="About", content="Content")
        admin = AboutPageAdmin(AboutPage, self.site)

        link = admin.public_link(page)

        self.assertIn("href='/hakkimizda/'", link)
        self.assertIn("Sayfayı Gör", link)

    def test_sidebar_widget_has_add_permission(self):
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        has_perm = admin.has_add_permission(self.request)

        self.assertFalse(has_perm)

    def test_sidebar_widget_has_delete_permission_existing_template(self):
        widget = SidebarWidget.objects.create(
            title="Test", template_name="includes/sidebar_popular_posts.html"
        )
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        has_perm = admin.has_delete_permission(self.request, obj=widget)

        self.assertFalse(has_perm)

    def test_sidebar_widget_has_delete_permission_missing_template(self):
        widget = SidebarWidget.objects.create(
            title="Test", template_name="includes/does_not_exist.html"
        )
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        has_perm = admin.has_delete_permission(self.request, obj=widget)

        self.assertTrue(has_perm)

    def test_sidebar_widget_has_delete_permission_no_obj(self):
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        has_perm = admin.has_delete_permission(self.request)

        self.assertFalse(has_perm)

    def test_sidebar_widget_sync_widgets(self):
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        admin.sync_widgets()

        self.assertTrue(
            SidebarWidget.objects.filter(template_name__contains="sidebar_").exists()
        )

    def test_sidebar_widget_get_queryset_calls_sync(self):
        SidebarWidget.objects.all().delete()
        admin = SidebarWidgetAdmin(SidebarWidget, self.site)

        qs = admin.get_queryset(self.request)

        self.assertTrue(qs.count() > 0)


class AboutPageImageInlineTests(TestCase):
    def setUp(self):
        self.site = default_site
        self.page = AboutPage.objects.create(title="About", content="Content")

    def test_thumb_no_pk(self):
        inline = AboutPageImageInline(AboutPage, self.site)
        obj = AboutPageImage()

        result = inline.thumb(obj)

        self.assertEqual(result, "—")

    def test_thumb_no_image(self):
        inline = AboutPageImageInline(AboutPage, self.site)
        obj = AboutPageImage(page=self.page)
        obj.save()

        result = inline.thumb(obj)

        self.assertEqual(result, "—")

    def test_thumb_with_image(self):
        inline = AboutPageImageInline(AboutPage, self.site)

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

        result = inline.thumb(obj)

        self.assertIn("<img src='", result)
        self.assertIn("class='admin-thumb'", result)

        obj.image.delete(save=False)
