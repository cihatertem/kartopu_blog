from decimal import Decimal
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.test import TestCase

from blog.cache_keys import (
    DIVIDEND_WIDGET_KEY,
    GOAL_WIDGET_KEY,
    SIDEBAR_WIDGETS_KEY,
    SITE_SETTINGS_KEY,
)
from core.context_processors import DIVIDEND_WIDGET_TEMPLATE_NAME
from core.models import SidebarWidget, SiteSettings
from core.signals import DIVIDEND_WIDGET_FRAGMENT_CACHE_NAME
from portfolio.models import DividendSnapshot, Portfolio, PortfolioSnapshot

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
    def test_dividend_sidebar_widget_post_save_invalidates_dividend_cache(
        self, mock_cache_delete
    ):
        SidebarWidget.objects.create(
            title="Temettü Geliri",
            template_name=DIVIDEND_WIDGET_TEMPLATE_NAME,
        )
        fragment_key = make_template_fragment_key(DIVIDEND_WIDGET_FRAGMENT_CACHE_NAME)
        mock_cache_delete.assert_has_calls(
            [
                call(SIDEBAR_WIDGETS_KEY),
                call(DIVIDEND_WIDGET_KEY),
                call(fragment_key),
            ]
        )

    @patch("core.signals.cache.delete")
    def test_dividend_snapshot_save_and_delete_invalidate_dividend_widget_cache(
        self, mock_cache_delete
    ):
        fragment_key = make_template_fragment_key(DIVIDEND_WIDGET_FRAGMENT_CACHE_NAME)
        snapshot = DividendSnapshot.objects.create(
            year=2026,
            currency="USD",
            total_amount=Decimal("3245.80"),
        )
        mock_cache_delete.assert_has_calls(
            [
                call(DIVIDEND_WIDGET_KEY),
                call(fragment_key),
            ]
        )

        mock_cache_delete.reset_mock()
        snapshot.delete()
        mock_cache_delete.assert_has_calls(
            [
                call(DIVIDEND_WIDGET_KEY),
                call(fragment_key),
            ]
        )

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
