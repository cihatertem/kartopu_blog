import os
from functools import cached_property

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator, slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit, Transpose

from core.imagekit import build_responsive_rendition
from core.images import optimize_uploaded_image_field
from core.mixins import TimeStampedModelMixin, UUIDModelMixin

META_TITLE_SUFFIX = " | Kartopu Money"
SEO_TITLE_MAX_LENGTH = 45
SEO_DESCRIPTION_MAX_LENGTH = 160
KARTOPU_MONEY_BASE_URL = "https://kartopu.money"


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
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    prefix = "cover"

    if not instance._state.adding:
        prefix = "cover_güncel"

    return f"blog/{slug}/{prefix}{timestamp}.{file_extension}"


def post_image_upload_path(instance: "BlogPostImage", filename: str) -> str:
    filename, file_extension = os.path.splitext(filename.lower())
    slug_filename = slugify(filename)
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    safe_name = f"{slug_filename}_{timestamp}"

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
        help_text=(
            "Blog içeriği (Markdown veya HTML).\n"
            "Markdown içinde kullanılabilen marker'lar:<br>\n"
            "  {{ image:1 }}  (1-based)<br>\n"
            "  {{ portfolio_summary:slug_or_hash }}<br>\n"
            "  {{ portfolio_charts:slug_or_hash }}<br>\n"
            "  {{ portfolio_category_summary:slug_or_hash }}<br>\n"
            "  {{ portfolio_comparison_summary:slug_or_hash }}<br>\n"
            "  {{ portfolio_comparison_charts:slug_or_hash }}<br>\n"
            "  {{ cashflow_summary:slug_or_hash }}<br>\n"
            "  {{ cashflow_charts:slug_or_hash }}<br>\n"
            "  {{ cashflow_comparison_summary:slug_or_hash }}<br>\n"
            "  {{ cashflow_comparison_charts:slug_or_hash }}<br>\n"
            "  {{ savings_rate_summary:slug_or_hash }}<br>\n"
            "  {{ savings_rate_charts:slug_or_hash }}<br>\n"
            "  {{ dividend_summary:slug_or_hash }}<br>\n"
            "  {{ dividend_charts:slug_or_hash }}<br>\n"
            "  {{ dividend_comparison:slug_or_hash }}<br>\n"
            "  {{ legal_disclaimer }}<br>"
        )
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

    cover_thumb_54 = ImageSpecField(
        source="cover_image",
        processors=[Transpose(), ResizeToFill(54, 54)],
        format="WEBP",
        options={"quality": 82},
    )

    cover_thumb_108 = ImageSpecField(
        source="cover_image",
        processors=[Transpose(), ResizeToFill(108, 108)],
        format="WEBP",
        options={"quality": 82},
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

    salary_savings_snapshots = models.ManyToManyField(
        "portfolio.SalarySavingsSnapshot",
        blank=True,
        related_name="blog_posts",
        help_text="Bu yazı ile ilişkili maaş/tasarruf snapshotları",
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

        if not self.canonical_url:
            self.canonical_url = KARTOPU_MONEY_BASE_URL + "/blog/" + self.slug + "/"

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

    @cached_property
    def cover_rendition(self) -> dict | None:
        if not self.cover_image:
            return None
        return build_responsive_rendition(
            original_field=self.cover_image,
            spec_map={
                600: self.cover_600,
                900: self.cover_900,
                1200: self.cover_1200,
            },
            largest_size=1200,
        )

    @cached_property
    def cover_thumb_rendition(self) -> dict | None:
        if not self.cover_image:
            return None
        return build_responsive_rendition(
            original_field=self.cover_image,
            spec_map={
                54: self.cover_thumb_54,
                108: self.cover_thumb_108,
            },
            largest_size=108,
        )


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

    @cached_property
    def rendition(self) -> dict | None:
        if not self.image:
            return None
        return build_responsive_rendition(
            original_field=self.image,
            spec_map={
                600: self.image_600,
                900: self.image_900,
                1200: self.image_1200,
            },
            largest_size=1200,
        )


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


class BlogPostReaction(
    TimeStampedModelMixin,
):
    class Reaction(models.TextChoices):
        ALKIS = "alkis", "Alkış"  # pyright: ignore[reportAssignmentType]
        ILHAM = "ilham", "İlham"  # pyright: ignore[reportAssignmentType]
        MERAK = "merak", "Merak"  # pyright: ignore[reportAssignmentType]
        KALP = "kalp", "Sevgi"  # pyright: ignore[reportAssignmentType]
        ROKET = "roket", "Gaz"  # pyright: ignore[reportAssignmentType]
        SURPRIZ = "surpriz", "Şaşkın"  # pyright: ignore[reportAssignmentType]
        MUTLU = "mutlu", "Mutlu"  # pyright: ignore[reportAssignmentType]
        DUYGULANDIM = "duygulandim", "Duygulandım"  # pyright: ignore[reportAssignmentType]
        DUSUNCELI = "dusunceli", "Düşünceli"  # pyright: ignore[reportAssignmentType]
        HUZUNLU = "huzunlu", "Hüzünlü"  # pyright: ignore[reportAssignmentType]
        RAHATSIZ = "rahatsiz", "Rahatsız"  # pyright: ignore[reportAssignmentType]
        KORKU = "korku", "Endişe"  # pyright: ignore[reportAssignmentType]

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_post_reactions",
    )
    reaction = models.CharField(max_length=20, choices=Reaction.choices)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Blog Tepkisi"
        verbose_name_plural = "Blog Tepkileri"
        constraints = (
            models.UniqueConstraint(
                fields=("post", "user"),
                name="unique_blog_post_reaction",
            ),
        )
        indexes = (models.Index(fields=("post", "reaction")),)

    def __str__(self) -> str:
        return f"{self.post.title} - {self.get_reaction_display()}"  # pyright: ignore[reportAttributeAccessIssue]
