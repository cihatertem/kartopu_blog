from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    Announcement,
    AnnouncementStatus,
    EmailQueue,
    EmailQueueStatus,
    Subscriber,
    SubscriberStatus,
)
from .services import send_announcement


@admin.action(description="Seçili abonelikleri iptal et")
def mark_unsubscribed(modeladmin, request, queryset):
    updated = queryset.update(
        status=SubscriberStatus.UNSUBSCRIBED, unsubscribed_at=timezone.now()
    )
    messages.success(request, f"{updated} abonelik iptal edildi.")


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "status",
        "subscribed_at",
        "confirmed_at",
        "unsubscribed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("email",)
    actions = (mark_unsubscribed,)
    ordering = ("-created_at",)


@admin.action(description="Seçili duyuruyu abonelere gönder")
def send_selected_announcements(modeladmin, request, queryset):
    for announcement in queryset:
        if announcement.status == AnnouncementStatus.SENT:
            messages.warning(request, f"{announcement.subject} zaten gönderildi.")
            continue
        sent_count = send_announcement(announcement)
        messages.success(
            request,
            f"{announcement.subject} duyurusu {sent_count} aboneye gönderildi.",
        )


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("subject", "status", "sent_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject",)
    actions = (send_selected_announcements,)


@admin.action(description="Seçili e-postaları tekrar bekliyor durumuna al")
def requeue_emails(modeladmin, request, queryset):
    updated = queryset.update(status=EmailQueueStatus.PENDING, error_message=None)
    messages.success(request, f"{updated} e-posta tekrar kuyruğa alındı.")


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display = ("subject", "to_email", "status", "sent_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "to_email")
    readonly_fields = ("created_at", "updated_at", "sent_at")
    actions = (requeue_emails,)
