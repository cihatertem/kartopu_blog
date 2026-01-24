import os
from functools import cached_property

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

from .imagekit import build_responsive_rendition
from .images import optimize_uploaded_image_field
from .mixins import TimeStampedModelMixin, UUIDModelMixin

SEO_TITLE_MAX_LENGTH = 45
SEO_DESCRIPTION_MAX_LENGTH = 160


class ContactMessage(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    MAX_MESSAGE_LENGTH = 3000

    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField(max_length=MAX_MESSAGE_LENGTH)
    website = models.CharField(max_length=255, blank=True)
    is_spam = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} - {self.subject}"


def about_image_upload_path(instance: "AboutPageImage", filename: str) -> str:
    filename, file_extension = os.path.splitext(filename.lower())
    safe_name = slugify(filename)
    return f"core/about/images/{safe_name}{file_extension}"


class AboutPage(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    title = models.CharField(max_length=120, default="Hakkımda")
    content = models.TextField(
        help_text="""Hakkımda sayfası içeriği (Markdown veya HTML).
        Markdown içinde kullanılabilen marker'lar:<br>
          {{ image:1 }}  (1-based)<br>"""
    )
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

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Hakkımda Sayfası"
        verbose_name_plural = "Hakkımda Sayfası"

    def clean(self) -> None:
        super().clean()
        if AboutPage.objects.exclude(pk=self.pk).exists():
            raise ValidationError("Sadece tek bir hakkımda sayfası olabilir.")

    def __str__(self) -> str:
        return str(self.title)


class AboutPageImage(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    page = models.ForeignKey(
        AboutPage,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to=about_image_upload_path,  # pyright: ignore[reportArgumentType]
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
        verbose_name = "Hakkımda Görseli"
        verbose_name_plural = "Hakkımda Görselleri"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new and self.image:
            try:
                optimize_uploaded_image_field(self.image)
            except Exception:
                pass

    def __str__(self) -> str:
        return f"{self.page.title} - Görsel"

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
