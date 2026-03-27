import uuid
from functools import cached_property

from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

from core.imagekit import build_responsive_rendition
from core.services.portfolio import generate_unique_slug


class TimeStampedModelMixin(models.Model):
    """
    A mixin that adds created_at and updated_at timestamp fields to a model.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ImageRenditionMixin(models.Model):
    """
    A mixin that provides common image renditions (600, 900, 1200) and a cached rendition property.
    Requires an 'image' field on the model.
    """

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

    class Meta:
        abstract = True

    @cached_property
    def rendition(self) -> dict | None:
        if not getattr(self, "image", None):
            return None
        return build_responsive_rendition(
            original_field=self.image,  # pyright: ignore[reportAttributeAccessIssue]
            spec_map={
                600: self.image_600,
                900: self.image_900,
                1200: self.image_1200,
            },
            largest_size=1200,
        )


class SlugMixin(models.Model):
    """
    A mixin that adds a unique slug field to a model, generated from its name.
    """

    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug and getattr(self, "name", None):
            self.slug = generate_unique_slug(self.__class__, self.name)  # pyright: ignore[reportAttributeAccessIssue]
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class UUIDModelMixin(models.Model):
    """
    A mixin that adds a UUID primary key field to a model.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="A unique identifier for the record.",
    )

    class Meta:
        abstract = True
