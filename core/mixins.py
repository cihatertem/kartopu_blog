import uuid

from django.db import models

from core.services.portfolio import generate_unique_slug


class TimeStampedModelMixin(models.Model):
    """
    A mixin that adds created_at and updated_at timestamp fields to a model.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
