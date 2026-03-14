from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone

from blog.admin import BlogPostAdmin, BlogPostImageInline, CategoryAdmin, TagAdmin
from blog.models import BlogPost, BlogPostImage, Category, Tag

User = get_user_model()


class MockRequest:
    def __init__(self, user=None):
        self.user = user

    def get_messages(self):
        return []


class BlogAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com", password="password"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="password", is_staff=True
        )
        self.category = Category.objects.create(name="Tech")
        self.post = BlogPost.objects.create(
            title="My Admin Post",
            author=self.admin_user,
            category=self.category,
            content="Content here",
            status=BlogPost.Status.DRAFT,
        )

    def test_tag_admin(self):
        model_admin = TagAdmin(Tag, self.site)
        self.assertEqual(model_admin.list_display, ("name", "slug"))
        self.assertEqual(model_admin.search_fields, ("name", "slug"))

    def test_category_admin(self):
        model_admin = CategoryAdmin(Category, self.site)
        self.assertEqual(model_admin.list_display, ("name", "slug", "created_at"))

    def test_blogpost_image_inline_thumb(self):
        inline = BlogPostImageInline(BlogPost, self.site)
        image = BlogPostImage(post=self.post)

        self.assertEqual(inline.thumb(image), "—")

        image.pk = 1
        image.image = MagicMock()
        image.image.url = "/media/test.jpg"

        with patch.object(
            inline, "_get_rendition_url", return_value="/media/rendition.jpg"
        ):
            html = inline.thumb(image)
            self.assertIn("class='admin-thumb'", html)
            self.assertIn("src='/media/rendition.jpg'", html)

        with patch.object(inline, "_get_rendition_url", return_value=None):
            html = inline.thumb(image)
            self.assertIn("class='admin-thumb'", html)
            self.assertIn("src='/media/test.jpg'", html)

    def test_blogpost_image_inline_get_rendition_url(self):
        inline = BlogPostImageInline(BlogPost, self.site)

        class MockImage:
            class MockImage600:
                url = "/media/rendition.jpg"

            image_600 = MockImage600()

        image = MockImage()

        url = inline._get_rendition_url(image)
        self.assertEqual(url, "/media/rendition.jpg")

        class BadImage:
            @property
            def image_600(self):
                raise Exception("Cannot resolve url")

        bad_image = BadImage()
        with self.assertLogs("blog.admin", level="ERROR"):
            url = inline._get_rendition_url(bad_image)
            self.assertIsNone(url)

    def test_blogpost_admin_actions(self):
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = MockRequest(user=self.admin_user)
        queryset = BlogPost.objects.filter(pk=self.post.pk)

        model_admin.publish_posts(request, queryset)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, BlogPost.Status.PUBLISHED)
        self.assertIsNotNone(self.post.published_at)

        model_admin.archive_posts(request, queryset)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, BlogPost.Status.ARCHIVED)

        model_admin.draft_posts(request, queryset)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, BlogPost.Status.DRAFT)

        self.assertFalse(self.post.is_featured)
        model_admin.toggle_is_featured(request, queryset)
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_featured)

    @patch("blog.admin.send_post_published_email")
    def test_resend_newsletter_notifications_action(self, mock_send):
        model_admin = BlogPostAdmin(BlogPost, self.site)

        request = self.factory.get("/")
        request.user = self.admin_user

        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        queryset = BlogPost.objects.filter(pk=self.post.pk)

        model_admin.resend_newsletter_notifications(request, queryset)
        mock_send.assert_not_called()

        self.post.status = BlogPost.Status.PUBLISHED
        self.post.published_at = timezone.now()
        self.post.save()

        queryset = BlogPost.objects.filter(pk=self.post.pk)

        model_admin.resend_newsletter_notifications(request, queryset)

        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][0].pk, self.post.pk)

    def test_formfield_for_foreignkey(self):
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = MockRequest()

        db_field = BlogPost._meta.get_field("author")
        formfield = model_admin.formfield_for_foreignkey(db_field, request)

        qs = formfield.queryset
        self.assertIn(self.staff_user, qs)

        normal_user = User.objects.create_user(
            email="normal@example.com", password="password"
        )
        self.assertNotIn(normal_user, qs)

    def test_get_changeform_initial_data(self):
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = self.factory.get("/")
        request.user = self.staff_user

        initial = model_admin.get_changeform_initial_data(request)
        self.assertEqual(initial["author"], self.staff_user.pk)

    def test_public_link(self):
        model_admin = BlogPostAdmin(BlogPost, self.site)

        html = model_admin.public_link(self.post)
        self.assertIn("preview", html)
        self.assertIn("Önizleme", html)

        self.post.status = BlogPost.Status.PUBLISHED
        self.post.save()
        html = model_admin.public_link(self.post)
        self.assertIn(self.post.get_absolute_url(), html)
        self.assertIn("Yayını Gör", html)

    def test_get_queryset_annotations(self):
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = MockRequest()
        qs = model_admin.get_queryset(request)

        post_from_qs = qs.get(pk=self.post.pk)
        self.assertTrue(hasattr(post_from_qs, "_reaction_count"))
        self.assertTrue(hasattr(post_from_qs, "_comment_count"))

        self.assertEqual(model_admin.reaction_count(post_from_qs), 0)
        self.assertEqual(model_admin.comment_count(post_from_qs), 0)
