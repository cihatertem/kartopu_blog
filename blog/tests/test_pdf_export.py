import io
from unittest.mock import MagicMock

from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from blog.admin import BlogPostAdmin
from blog.models import BlogPost, BlogPostImage, Category, Tag
from blog.pdf import generate_published_posts_pdf

User = get_user_model()


class MockRequest:
    def __init__(self, user=None):
        self.user = user
        self.GET = {}
        self._messages = []

    def get_messages(self):
        return self._messages


class PDFExportTestCase(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin_user = User.objects.create_superuser(
            email="pdf_admin@example.com", password="password"
        )
        self.category = Category.objects.create(name="Finans", slug="finans")
        self.tag1 = Tag.objects.create(name="Borsa", slug="borsa")
        self.tag2 = Tag.objects.create(name="Tasarruf", slug="tasarruf")

        # 1. Published Post with cover, tags, headings, content & markers
        self.published_post = BlogPost.objects.create(
            title="Yayınlanmış Finans Yazısı",
            author=self.admin_user,
            category=self.category,
            excerpt="Finansal özgürlük özeti.",
            content=(
                "# Ana Başlık\n"
                "## Alt Başlık 1\n"
                "Bu bir test paragrafıdır.\n"
                "{{ image:1 }}\n"
                "{{ portfolio_summary }}\n"
                "### Alt Başlık 2\n"
                "Son paragraf."
            ),
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.published_post.tags.add(self.tag1, self.tag2)

        # Attach inline image
        small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
            b"\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
            b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
        )
        self.inline_image = BlogPostImage.objects.create(
            post=self.published_post,
            image=SimpleUploadedFile("test_inline.gif", small_gif, content_type="image/gif"),
            caption="Inline Görsel Açıklaması",
            alt_text="Inline Görsel",
            order=1,
        )

        # 2. Draft Post (Must be excluded)
        self.draft_post = BlogPost.objects.create(
            title="Taslak Yazı",
            author=self.admin_user,
            category=self.category,
            content="Taslak içerik",
            status=BlogPost.Status.DRAFT,
        )

        # 3. Archived Post (Must be excluded)
        self.archived_post = BlogPost.objects.create(
            title="Arşivlenmiş Yazı",
            author=self.admin_user,
            category=self.category,
            content="Arşivlenmiş içerik",
            status=BlogPost.Status.ARCHIVED,
        )

    def test_generate_published_posts_pdf_valid_bytes(self):
        """Verify that generate_published_posts_pdf produces valid PDF byte stream

        containing only published posts.
        """
        queryset = BlogPost.objects.all()
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 500)

    def test_generate_published_posts_pdf_empty_if_no_published(self):
        """Verify PDF generation when queryset contains only draft/archived posts."""
        queryset = BlogPost.objects.filter(status__in=[BlogPost.Status.DRAFT, BlogPost.Status.ARCHIVED])
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_admin_action_export_published_posts_pdf_success(self):
        """Verify admin action returns HTTP 200 response with attachment when published posts exist."""
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = MockRequest(user=self.admin_user)

        queryset = BlogPost.objects.filter(pk__in=[self.published_post.pk, self.draft_post.pk])
        response = model_admin.export_published_posts_pdf(request, queryset)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_admin_action_export_published_posts_pdf_warning_when_no_published(self):
        """Verify admin action shows warning message when selected posts contain no published posts."""
        model_admin = BlogPostAdmin(BlogPost, self.site)
        request = MockRequest(user=self.admin_user)
        model_admin.message_user = MagicMock()

        queryset = BlogPost.objects.filter(pk__in=[self.draft_post.pk, self.archived_post.pk])
        response = model_admin.export_published_posts_pdf(request, queryset)

        self.assertIsNone(response)
        model_admin.message_user.assert_called_once_with(
            request,
            "Seçilen yazılar arasında yayınlanmış yazı bulunamadı.",
            level=messages.WARNING,
        )
