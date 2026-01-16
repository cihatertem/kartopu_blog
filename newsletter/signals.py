from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from blog.models import BlogPost

from .models import BlogPostNotification
from .services import send_post_published_email


@receiver(post_save, sender=BlogPost)
def notify_subscribers_on_publish(sender, instance: BlogPost, **kwargs):
    if instance.status != BlogPost.Status.PUBLISHED or not instance.published_at:
        return

    if BlogPostNotification.objects.filter(post=instance).exists():
        return

    def _send_notification():
        send_post_published_email(instance)
        BlogPostNotification.objects.create(post=instance, sent_at=timezone.now())

    transaction.on_commit(_send_notification)
