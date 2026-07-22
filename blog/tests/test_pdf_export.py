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

    def test_generate_published_posts_pdf_turkish_characters(self):
        """Verify that posts containing full Turkish unicode characters render without errors."""
        post_tr = BlogPost.objects.create(
            title="Şemsiye & Çağlayan: Iğdır'da Öğretmen İşçi ve Güneş",
            author=self.admin_user,
            category=self.category,
            excerpt="Şiirsel bir Türkçe içerik özeti: ğüşiöç ĞÜŞİÖÇ IİıŞşĞğ",
            content=(
                "# ĞÜŞİÖÇ Başlık\n"
                "## Alt Başlık: Şiir ve Ğazel\n"
                "Bu paragrafta **kalın Türkçe metin: şemsiye, öğretmen, ığdır** bulunmaktadır.\n"
                "*İtalik Türkçe metin: çağlayan ve güneş.*"
            ),
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        post_tr.tags.add(self.tag1)

        queryset = BlogPost.objects.filter(pk=post_tr.pk)
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 500)

    def test_generate_published_posts_pdf_with_charts_and_markers(self):
        """Verify that posts containing financial charts and marker placeholders render cleanly."""
        post_markers = BlogPost.objects.create(
            title="Finansal Özetler ve Grafik Raporu",
            author=self.admin_user,
            category=self.category,
            excerpt="Grafik ve tablo içeren test yazısı.",
            content=(
                "# Portföy Analizi\n"
                "{{ portfolio_summary }}\n"
                "{{ portfolio_charts }}\n"
                "{{ portfolio_category_summary }}\n"
                "{{ portfolio_irr_charts }}\n"
                "{{ portfolio_comparison_summary }}\n"
                "{{ portfolio_comparison_charts }}\n"
                "{{ cashflow_summary }}\n"
                "{{ cashflow_charts }}\n"
                "{{ savings_rate_summary }}\n"
                "{{ savings_rate_charts }}\n"
                "{{ dividend_summary }}\n"
                "{{ dividend_charts }}\n"
                "{{ dividend_comparison }}\n"
                "{{ legal_disclaimer }}"
            ),
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        queryset = BlogPost.objects.filter(pk=post_markers.pk)
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_generate_published_posts_pdf_with_dividend_payment_item(self):
        """Verify that DividendSnapshotPaymentItem objects with total_net_amount render without AttributeError."""
        from portfolio.models import (
            Asset,
            DividendPayment,
            DividendSnapshot,
            DividendSnapshotPaymentItem,
        )

        from decimal import Decimal

        asset = Asset.objects.create(symbol="USD", name="Dolar", asset_type="cash")
        snapshot = DividendSnapshot.objects.create(
            year=2026, total_amount=Decimal("1500"), currency="TRY"
        )
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date=timezone.now().date(),
            share_count=Decimal("100"),
            net_dividend_per_share=Decimal("15.0"),
            average_cost=Decimal("100.0"),
            last_close_price=Decimal("200.0"),
        )
        DividendSnapshotPaymentItem.objects.create(
            snapshot=snapshot,
            asset=asset,
            payment=payment,
            payment_date=timezone.now().date(),
            per_share_net_amount=Decimal("15.0"),
            dividend_yield_on_payment_price=Decimal("0.05"),
            dividend_yield_on_average_cost=Decimal("0.08"),
            total_net_amount=Decimal("1500.0"),
        )

        post_div = BlogPost.objects.create(
            title="Temettü Ödemesi Testi",
            author=self.admin_user,
            category=self.category,
            content="## Temettü Dökümü\n{{ dividend_summary:1 }}",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        post_div.dividend_snapshots.add(snapshot)

        queryset = BlogPost.objects.filter(pk=post_div.pk)
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 500)

    def test_generate_published_posts_pdf_with_portfolio_snapshot_item(self):
        """Verify that PortfolioSnapshotItem objects with market_value render without AttributeError."""
        from decimal import Decimal
        from portfolio.models import (
            Asset,
            Portfolio,
            PortfolioSnapshot,
            PortfolioSnapshotItem,
        )

        portfolio = Portfolio.objects.create(
            owner=self.admin_user,
            name="Ana Portföy",
            currency="TRY",
            target_value=Decimal("100000"),
        )
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            snapshot_date=timezone.now().date(),
            period="monthly",
            total_value=Decimal("50000"),
            total_cost=Decimal("40000"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("0.25"),
        )
        asset = Asset.objects.create(symbol="USD", name="Dolar", asset_type="cash")
        PortfolioSnapshotItem.objects.create(
            snapshot=snapshot,
            asset=asset,
            quantity=Decimal("100"),
            average_cost=Decimal("400"),
            cost_basis=Decimal("40000"),
            current_price=Decimal("500"),
            market_value=Decimal("50000"),
            allocation_pct=Decimal("1.0"),
            gain_loss=Decimal("10000"),
            gain_loss_pct=Decimal("0.25"),
        )

        post_port = BlogPost.objects.create(
            title="Portföy Testi",
            author=self.admin_user,
            category=self.category,
            content="## Portföy Varlıkları\n{{ portfolio_charts:1 }}\n{{ portfolio_category_summary:1 }}",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        post_port.portfolio_snapshots.add(snapshot)

        queryset = BlogPost.objects.filter(pk=post_port.pk)
        pdf_bytes = generate_published_posts_pdf(queryset)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_bytes), 500)
