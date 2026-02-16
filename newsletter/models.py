from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.mixins import TimeStampedModelMixin, UUIDModelMixin


class SubscriberStatus(models.TextChoices):
    PENDING = "pending", "Onay Bekliyor"
    ACTIVE = "active", "Aktif"
    UNSUBSCRIBED = "unsubscribed", "İptal Edildi"


class Subscriber(UUIDModelMixin, TimeStampedModelMixin):
    email = models.EmailField(unique=True)
    status = models.CharField(
        max_length=20,
        choices=SubscriberStatus.choices,
        default=SubscriberStatus.PENDING,
    )
    subscribed_at = models.DateTimeField(blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        ordering = ("-created_at",)
        verbose_name = "Newsletter Abonesi"
        verbose_name_plural = "Newsletter Aboneleri"

    def __str__(self) -> str:
        return self.email

    def mark_pending(self) -> None:
        self.status = SubscriberStatus.PENDING
        self.subscribed_at = timezone.now()
        self.unsubscribed_at = None
        self.save(update_fields=["status", "subscribed_at", "unsubscribed_at"])

    def activate(self) -> None:
        self.status = SubscriberStatus.ACTIVE
        if self.subscribed_at is None:
            self.subscribed_at = timezone.now()
        self.confirmed_at = timezone.now()
        self.unsubscribed_at = None
        self.save(
            update_fields=[
                "status",
                "subscribed_at",
                "confirmed_at",
                "unsubscribed_at",
            ]
        )

    def unsubscribe(self) -> None:
        self.status = SubscriberStatus.UNSUBSCRIBED
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["status", "unsubscribed_at"])


class BlogPostNotification(UUIDModelMixin, TimeStampedModelMixin):
    post = models.OneToOneField(
        "blog.BlogPost",
        on_delete=models.CASCADE,
        related_name="newsletter_notification",
    )
    sent_at = models.DateTimeField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Yazı Bildirimi"
        verbose_name_plural = "Yazı Bildirimleri"

    def __str__(self) -> str:
        return f"{self.post.title}"  # pyright: ignore[reportAttributeAccessIssue]


class AnnouncementStatus(models.TextChoices):
    DRAFT = "draft", "Taslak"
    SENT = "sent", "Gönderildi"


class Announcement(UUIDModelMixin, TimeStampedModelMixin):
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=AnnouncementStatus.choices,
        default=AnnouncementStatus.DRAFT,
    )
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Özel Duyuru"
        verbose_name_plural = "Özel Duyurular"

    def __str__(self) -> str:
        return self.subject


class EmailQueueStatus(models.TextChoices):
    PENDING = "pending", "Bekliyor"
    PROCESSING = "processing", "İşleniyor"
    SENT = "sent", "Gönderildi"
    FAILED = "failed", "Hata Oluştu"


class EmailQueue(UUIDModelMixin, TimeStampedModelMixin):
    subject = models.CharField(max_length=255)
    from_email = models.EmailField()
    to_email = models.EmailField()
    text_body = models.TextField()
    html_body = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=EmailQueueStatus.choices,
        default=EmailQueueStatus.PENDING,
    )
    sent_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    direct_email = models.ForeignKey(
        "DirectEmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_items",
        verbose_name="Doğrudan E-posta",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "E-posta Kuyruğu"
        verbose_name_plural = "E-posta Kuyruğu"
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.subject} -> {self.to_email}"


def direct_email_attachment_path(instance, filename: str) -> str:
    subject_slug = slugify(instance.direct_email.subject)
    return f"mail/{subject_slug}/{filename}"


class DirectEmail(UUIDModelMixin, TimeStampedModelMixin):
    to_email = models.EmailField(verbose_name="Alıcı (To)")
    subject = models.CharField(max_length=255, verbose_name="Konu (Subject)")
    body = models.TextField(
        verbose_name="İçerik (Body)", help_text="Markdown formatında yazabilirsiniz."
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Gönderilme Tarihi"
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Doğrudan E-posta"
        verbose_name_plural = "Doğrudan E-postalar"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.subject} -> {self.to_email}"


class DirectEmailAttachment(UUIDModelMixin, TimeStampedModelMixin):
    direct_email = models.ForeignKey(
        DirectEmail,
        related_name="attachments",
        on_delete=models.CASCADE,
        verbose_name="E-posta",
    )
    file = models.FileField(
        upload_to=direct_email_attachment_path, verbose_name="Dosya"
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "E-posta Eki"
        verbose_name_plural = "E-posta Ekleri"

    def __str__(self) -> str:
        return self.file.name
