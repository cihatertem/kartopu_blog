from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from blog.models import BlogPost

from .services import queue_post_published_notification


@receiver(post_save, sender=BlogPost)
def notify_subscribers_on_publish(sender, instance: BlogPost, **kwargs):
    if instance.status != BlogPost.Status.PUBLISHED or not instance.published_at:
        return

    transaction.on_commit(lambda: queue_post_published_notification(instance))
