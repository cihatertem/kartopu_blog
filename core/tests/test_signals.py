from unittest.mock import patch

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

    @patch("core.signals.cache.delete")
    def test_portfolio_snapshot_post_save_invalidates_cache(self, mock_cache_delete):
        PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            total_value=100,
            total_cost=80,
            target_value=100,
            total_return_pct=25,
        )
        mock_cache_delete.assert_called_once_with(GOAL_WIDGET_KEY)

    @patch("core.signals.cache.delete")
    def test_portfolio_snapshot_post_delete_invalidates_cache(self, mock_cache_delete):
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            total_value=100,
            total_cost=80,
            target_value=100,
            total_return_pct=25,
        )
        mock_cache_delete.reset_mock()
        snapshot.delete()
        mock_cache_delete.assert_called_once_with(GOAL_WIDGET_KEY)

    @patch("core.signals.cache.delete")
    def test_sidebar_widget_post_save_invalidates_cache(self, mock_cache_delete):
        SidebarWidget.objects.create(title="Widget", template_name="widget.html")
        mock_cache_delete.assert_called_once_with(SIDEBAR_WIDGETS_KEY)

    @patch("core.signals.cache.delete")
    def test_sidebar_widget_post_delete_invalidates_cache(self, mock_cache_delete):
        widget = SidebarWidget.objects.create(
            title="Widget", template_name="widget.html"
        )
        mock_cache_delete.reset_mock()  # Reset because save also triggers delete
        widget.delete()
        mock_cache_delete.assert_called_once_with(SIDEBAR_WIDGETS_KEY)

    @patch("core.signals.cache.delete")
    def test_site_settings_post_save_invalidates_cache(self, mock_cache_delete):
        settings = SiteSettings.get_settings()
        mock_cache_delete.reset_mock()
        settings.is_comments_enabled = False
        settings.save()
        mock_cache_delete.assert_called_once_with(SITE_SETTINGS_KEY)

    @patch("core.signals.cache.delete")
    def test_site_settings_post_delete_invalidates_cache(self, mock_cache_delete):
        settings = SiteSettings.get_settings()
        mock_cache_delete.reset_mock()  # Reset because get_settings/create might trigger save
        settings.delete()
        mock_cache_delete.assert_called_once_with(SITE_SETTINGS_KEY)
