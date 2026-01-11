from django.db import models

from .mixins import TimeStampedModelMixin, UUIDModelMixin


# Create your models here.
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
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} - {self.subject}"
