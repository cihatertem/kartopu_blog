from django.conf import settings
from django.db import models

from core.mixins import TimeStampedModelMixin, UUIDModelMixin

MAX_COMMENT_LENGTH = 3000


class Comment(
    UUIDModelMixin,
    TimeStampedModelMixin,
):
    class Status(models.TextChoices):
        PENDING = "pending", "Onay Bekliyor"  # pyright: ignore[reportAssignmentType]
        APPROVED = "approved", "Onaylandı"  # pyright: ignore[reportAssignmentType]
        REJECTED = "rejected", "Reddedildi"  # pyright: ignore[reportAssignmentType]
        SPAM = "spam", "Spam"  # pyright: ignore[reportAssignmentType]

    post = models.ForeignKey(
        "blog.BlogPost",
        on_delete=models.CASCADE,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="replies",
        blank=True,
        null=True,
    )

    body = models.TextField(max_length=MAX_COMMENT_LENGTH)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING.value,
    )

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    social_provider = models.CharField(max_length=50, blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-created_at"]
        verbose_name = "Yorum"
        verbose_name_plural = "Yorumlar"
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.post.title} - {self.author.full_name}"

    @property
    def is_public(self) -> bool:
        return self.status == self.Status.APPROVED
