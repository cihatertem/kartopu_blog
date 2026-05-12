from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from blog.cache_keys import GOAL_WIDGET_KEY, SIDEBAR_WIDGETS_KEY, SITE_SETTINGS_KEY
from core.models import SidebarWidget, SiteSettings
from portfolio.models import Portfolio, PortfolioSnapshot

User = get_user_model()


class SignalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=100
        )

    def test_portfolio_snapshot_post_save_invalidates_cache(self):
        cache.set(GOAL_WIDGET_KEY, "cached_data")
        PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            total_value=100,
            total_cost=80,
            target_value=100,
            total_return_pct=25,
        )
        self.assertIsNone(cache.get(GOAL_WIDGET_KEY))

    def test_portfolio_snapshot_post_delete_invalidates_cache(self):
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            total_value=100,
            total_cost=80,
            target_value=100,
            total_return_pct=25,
        )
        cache.set(GOAL_WIDGET_KEY, "cached_data")
        snapshot.delete()
        self.assertIsNone(cache.get(GOAL_WIDGET_KEY))

    def test_sidebar_widget_post_save_invalidates_cache(self):
        cache.set(SIDEBAR_WIDGETS_KEY, "cached_data")
        SidebarWidget.objects.create(title="Widget", template_name="widget.html")
        self.assertIsNone(cache.get(SIDEBAR_WIDGETS_KEY))

    def test_sidebar_widget_post_delete_invalidates_cache(self):
        widget = SidebarWidget.objects.create(
            title="Widget", template_name="widget.html"
        )
        cache.set(SIDEBAR_WIDGETS_KEY, "cached_data")
        widget.delete()
        self.assertIsNone(cache.get(SIDEBAR_WIDGETS_KEY))

    def test_site_settings_post_save_invalidates_cache(self):
        settings = SiteSettings.get_settings()
        cache.set(SITE_SETTINGS_KEY, "cached_data")
        settings.is_comments_enabled = False
        settings.save()
        self.assertIsNone(cache.get(SITE_SETTINGS_KEY))

    def test_site_settings_post_delete_invalidates_cache(self):
        settings = SiteSettings.get_settings()
        cache.set(SITE_SETTINGS_KEY, "cached_data")
        settings.delete()
        self.assertIsNone(cache.get(SITE_SETTINGS_KEY))
