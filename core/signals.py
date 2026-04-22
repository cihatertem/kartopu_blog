from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import GOAL_WIDGET_KEY, SIDEBAR_WIDGETS_KEY, SITE_SETTINGS_KEY
from core.models import SidebarWidget, SiteSettings
from portfolio.models import PortfolioSnapshot


@receiver(post_save, sender=PortfolioSnapshot)
@receiver(post_delete, sender=PortfolioSnapshot)
def invalidate_goal_widget_cache(sender, instance, **kwargs):
    if instance.is_featured:
        cache.delete(GOAL_WIDGET_KEY)


@receiver(post_save, sender=SidebarWidget)
@receiver(post_delete, sender=SidebarWidget)
def invalidate_sidebar_widget_cache(sender, instance, **kwargs):
    cache.delete(SIDEBAR_WIDGETS_KEY)


@receiver(post_save, sender=SiteSettings)
@receiver(post_delete, sender=SiteSettings)
def invalidate_site_settings_cache(sender, instance, **kwargs):
    cache.delete(SITE_SETTINGS_KEY)
