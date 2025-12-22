import os

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

from core.images import optimize_uploaded_image
from core.mixins import TimeStampedModelMixin, UUIDModelMixin


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
    models.Model,
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
    title = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL ve SEO için kullanılır.",
    )
    excerpt = models.TextField(
        blank=True,
        help_text="Listeleme sayfalarında gösterilecek kısa özet.",
    )
    content = models.TextField(help_text="Blog içeriği (Markdown veya HTML).")

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
        max_length=255,
        blank=True,
    )
    meta_description = models.CharField(
        max_length=300,
        blank=True,
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

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Blog Yazısı"
        verbose_name_plural = "Blog Yazıları"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "published_at"]),
        ]

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
                optimize_uploaded_image(self.cover_image.path)
            except Exception:
                pass

    def get_absolute_url(self) -> str:
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def effective_meta_title(self) -> str:
        """Template usage: <meta name="description" content="{{ post.effective_meta_title }}">"""
        return str(self.meta_title) or str(self.title)

    @property
    def effective_meta_description(self) -> str:
        """Template usage: <meta name="description" content="{{ post.effective_meta_description }}">"""
        return str(self.meta_description) or str(self.excerpt)[:300]


class BlogPostImage(
    UUIDModelMixin,
    TimeStampedModelMixin,
    models.Model,
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
                optimize_uploaded_image(self.image.path)
            except Exception:
                pass

    def __str__(self) -> str:
        return f"{self.post.title} - Görsel"  # pyright: ignore[reportAttributeAccessIssue]
