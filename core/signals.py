from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import (
    DIVIDEND_WIDGET_KEY,
    GOAL_WIDGET_KEY,
    SIDEBAR_WIDGETS_KEY,
    SITE_SETTINGS_KEY,
)
from core.context_processors import DIVIDEND_WIDGET_TEMPLATE_NAME
from core.models import SidebarWidget, SiteSettings
from portfolio.models import DividendSnapshot, PortfolioSnapshot

DIVIDEND_WIDGET_FRAGMENT_CACHE_NAME = "sidebar_dividend_widget"


def invalidate_dividend_widget_cache(*args, **kwargs):
    cache.delete(DIVIDEND_WIDGET_KEY)
    cache.delete(make_template_fragment_key(DIVIDEND_WIDGET_FRAGMENT_CACHE_NAME))


@receiver(post_save, sender=PortfolioSnapshot)
@receiver(post_delete, sender=PortfolioSnapshot)
def invalidate_goal_widget_cache(sender, instance, **kwargs):
    cache.delete(GOAL_WIDGET_KEY)


@receiver(post_save, sender=DividendSnapshot)
@receiver(post_delete, sender=DividendSnapshot)
def invalidate_dividend_snapshot_widget_cache(sender, instance, **kwargs):
    invalidate_dividend_widget_cache()


@receiver(post_save, sender=SidebarWidget)
@receiver(post_delete, sender=SidebarWidget)
def invalidate_sidebar_widget_cache(sender, instance, **kwargs):
    cache.delete(SIDEBAR_WIDGETS_KEY)
    if (
        instance.template_name == DIVIDEND_WIDGET_TEMPLATE_NAME
        or instance.current_dividend_snapshot_id
        or instance.previous_dividend_snapshot_id
    ):
        invalidate_dividend_widget_cache()


@receiver(post_save, sender=SiteSettings)
@receiver(post_delete, sender=SiteSettings)
def invalidate_site_settings_cache(sender, instance, **kwargs):
    cache.delete(SITE_SETTINGS_KEY)
