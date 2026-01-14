import os

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from django.urls import reverse
from django.utils.text import Truncator, slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

from core.images import optimize_uploaded_image_field
from core.mixins import TimeStampedModelMixin, UUIDModelMixin

META_TITLE_SUFFIX = " | Kartopu Blog"
SEO_TITLE_MAX_LENGTH = 45
SEO_DESCRIPTION_MAX_LENGTH = 160


class Category(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(
        blank=True,
        max_length=SEO_DESCRIPTION_MAX_LENGTH,
        help_text="Kategori açıklaması (SEO için) max 160 karakter.",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"
        ordering = ("name",)
        indexes = (models.Index(fields=["slug"]),)

    def __str__(self) -> str:
        return str(self.name)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog:category_detail", kwargs={"slug": self.slug})


def post_cover_upload_path(instance: "BlogPost", filename: str) -> str:
    file_extension = filename.split(".")[-1].lower()
    slug = instance.slug or slugify(instance.title)

    return f"blog/{slug}/cover.{file_extension}"


def post_image_upload_path(instance: "BlogPostImage", filename: str) -> str:
    filename, file_extension = os.path.splitext(filename.lower())
    safe_name = slugify(filename)

    return f"blog/{instance.post.slug}/images/{safe_name}{file_extension}"  # pyright: ignore[reportAttributeAccessIssue]


class BlogPost(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"  # pyright: ignore[reportAssignmentType]
        PUBLISHED = "published", "Yayınlandı"  # pyright: ignore[reportAssignmentType]
        ARCHIVED = "archived", "Arşivlendi"  # pyright: ignore[reportAssignmentType]

    # --- İlişkiler ---
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
    )

    # --- İçerik ---
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="posts",
        blank=True,
        null=True,
    )

    tags = models.ManyToManyField(
        "Tag",
        related_name="posts",
        blank=True,
        help_text="Yazı ile ilişkili etiketler",
    )

    title = models.CharField(
        max_length=SEO_TITLE_MAX_LENGTH,
        help_text="Yazı başlığı. Max 45 karakter.",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL ve SEO için kullanılır.",
    )
    excerpt = models.TextField(
        blank=True,
        help_text="Listeleme sayfalarında gösterilecek kısa özet.",
    )
    content = models.TextField(
        help_text="""Blog içeriği (Markdown veya HTML).
        Markdown içinde kullanılabilen marker'lar:<br>
          {{ image:1 }}  (1-based)<br>
          {{ portfolio_summary:slug_or_hash }}<br>
          {{ portfolio_charts:slug_or_hash }}<br>
          {{ portfolio_category_summary:slug_or_hash }}<br>
          {{ portfolio_comparison_summary:slug_or_hash }}<br>
          {{ portfolio_comparison_charts:slug_or_hash }}<br>
          {{ cashflow_summary:slug_or_hash }}<br>
          {{ cashflow_charts:slug_or_hash }}<br>
          {{ cashflow_comparison_summary:slug_or_hash }}<br>
          {{ cashflow_comparison_charts:slug_or_hash }}<br>
          {{ dividend_summary:slug_or_hash }}<br>
          {{ dividend_charts:slug_or_hash }}<br>
          {{ dividend_comparison:slug_or_hash }}<br>
          {{ legal_disclaimer }}<br>"""
    )

    # --- Yayın durumu ---
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT.value,
    )
    published_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Yayınlanma zamanı.",
    )

    # --- Medya ---
    cover_image = models.ImageField(
        upload_to=post_cover_upload_path,  # pyright: ignore[reportArgumentType]
        blank=True,
        null=True,
    )

    # --- SEO ---
    meta_title = models.CharField(
        max_length=SEO_TITLE_MAX_LENGTH,
        blank=True,
        help_text="SEO title (önerilen: 35–45 karakter 45 max).",
    )
    meta_description = models.CharField(
        max_length=SEO_DESCRIPTION_MAX_LENGTH,
        blank=True,
        help_text="SEO description (önerilen: 140–160 karakter)",
    )
    canonical_url = models.URLField(
        blank=True,
    )

    # --- UX / Görünürlük ---
    is_featured = models.BooleanField(
        default=False,  # pyright: ignore[reportArgumentType]
        help_text="Anasayfada öne çıkar.",
    )
    view_count = models.PositiveIntegerField(default=0)  # pyright: ignore[reportArgumentType]

    # imagekit
    cover_600 = ImageSpecField(
        source="cover_image",
        processors=[Transpose(), ResizeToFit(600, 600)],
        format="WEBP",
        options={"quality": 85},
    )

    cover_900 = ImageSpecField(
        source="cover_image",
        processors=[Transpose(), ResizeToFit(900, 900)],
        format="WEBP",
        options={"quality": 85},
    )

    cover_1200 = ImageSpecField(
        source="cover_image",
        processors=[Transpose(), ResizeToFit(1200, 1200)],
        format="WEBP",
        options={"quality": 85},
    )

    portfolio_snapshots = models.ManyToManyField(
        "portfolio.PortfolioSnapshot",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili portföy özetleri (snapshot)",
    )

    portfolio_comparisons = models.ManyToManyField(
        "portfolio.PortfolioComparison",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili portföy karşılaştırmaları",
    )

    cashflow_snapshots = models.ManyToManyField(
        "portfolio.CashFlowSnapshot",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili nakit akışı snapshotları",
    )

    cashflow_comparisons = models.ManyToManyField(
        "portfolio.CashFlowComparison",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili nakit akışı karşılaştırmaları",
    )

    dividend_snapshots = models.ManyToManyField(
        "portfolio.DividendSnapshot",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili temettü snapshotları",
    )

    dividend_comparisons = models.ManyToManyField(
        "portfolio.DividendComparison",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili temettü karşılaştırmaları",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Blog Yazısı"
        verbose_name_plural = "Blog Yazıları"

        indexes = (
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "published_at"]),
            GinIndex(
                SearchVector("title", "excerpt", "content", config="turkish"),
                name="blogpost_fts_gin",
            ),
        )

    def __str__(self) -> str:
        return str(self.title)

    def save(self, *args, **kwargs):
        # slug otomatik üret
        if not self.slug:
            self.slug = slugify(self.title)

        if self.status == self.Status.PUBLISHED and self.published_at is None:
            from django.utils import timezone

            self.published_at = timezone.now()

        is_new = self._state.adding

        super().save(*args, **kwargs)

        if is_new and self.cover_image:
            try:
                optimize_uploaded_image_field(self.cover_image)
            except Exception:
                pass

    def get_absolute_url(self) -> str:
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def effective_meta_title(self) -> str:
        """Template usage: <title> {{ post.effective_meta_title }} </title>"""
        suffix = META_TITLE_SUFFIX
        base_meta_title = self.meta_title or self.title
        meta_title = str(base_meta_title).strip() + suffix

        return Truncator(meta_title).chars(60)

    @property
    def effective_meta_description(self) -> str:
        """Template usage: <meta name="description" content="{{ post.effective_meta_description }}">"""
        base = self.meta_description or self.excerpt or ""
        return Truncator(base).chars(160)


class BlogPostImage(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to=post_image_upload_path,  # pyright: ignore[reportArgumentType]
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Erişilebilirlik ve SEO için",
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Görsel alt yazısı",
    )

    order = models.PositiveSmallIntegerField(
        default=0,  # pyright: ignore[reportArgumentType]
        help_text="Görsel sırası",
    )

    # imagekit
    image_600 = ImageSpecField(
        source="image",
        processors=[Transpose(), ResizeToFit(600, 600)],
        format="WEBP",
        options={"quality": 85},
    )

    image_900 = ImageSpecField(
        source="image",
        processors=[Transpose(), ResizeToFit(900, 900)],
        format="WEBP",
        options={"quality": 85},
    )

    image_1200 = ImageSpecField(
        source="image",
        processors=[Transpose(), ResizeToFit(1200, 1200)],
        format="WEBP",
        options={"quality": 85},
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["order"]
        verbose_name = "Blog Görseli"
        verbose_name_plural = "Blog Görselleri"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        # Sadece ilk upload'ta optimize et
        if is_new and self.image:
            try:
                optimize_uploaded_image_field(self.image)
            except Exception:
                pass

    def __str__(self) -> str:
        return f"{self.post.title} - Görsel"  # pyright: ignore[reportAttributeAccessIssue]


class Tag(
    TimeStampedModelMixin,
    UUIDModelMixin,
):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ("name",)
        verbose_name = "Etiket"
        verbose_name_plural = "Etiketler"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("blog:tag_detail", kwargs={"slug": self.slug})
