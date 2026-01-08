from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import NAV_KEYS

from .models import Comment


@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def comment_changed(sender, **kwargs):
    cache.delete_many(NAV_KEYS)
