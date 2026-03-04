from django.apps import apps
from django.test import SimpleTestCase

from portfolio.apps import PortfolioConfig


class PortfolioConfigTests(SimpleTestCase):
    def test_apps(self):
        self.assertEqual(PortfolioConfig.name, "portfolio")
        self.assertEqual(apps.get_app_config("portfolio").name, "portfolio")
        self.assertEqual(
            PortfolioConfig.default_auto_field, "django.db.models.BigAutoField"
        )
