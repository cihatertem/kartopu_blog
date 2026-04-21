from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from portfolio.models import PortfolioSnapshot
from core.cache_keys import GOAL_WIDGET_KEY

@receiver(post_save, sender=PortfolioSnapshot)
@receiver(post_delete, sender=PortfolioSnapshot)
def invalidate_goal_widget_cache(sender, instance, **kwargs):
    if instance.is_featured:
        cache.delete(GOAL_WIDGET_KEY)
