import uuid

from django.db import models


class TimeStampedModelMixin(models.Model):
    """
    A mixin that adds created_at and updated_at timestamp fields to a model.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
