from django.apps import apps
from django.test import TestCase

from accounts.apps import AccountsConfig


class AccountsConfigTests(TestCase):
    def setUp(self):
        # Arrange
        self.expected_app_name = "accounts"
        self.app_config = apps.get_app_config(self.expected_app_name)

    def test_apps(self):
        # Act & Assert
        self.assertEqual(AccountsConfig.name, self.expected_app_name)
        self.assertEqual(self.app_config.name, self.expected_app_name)
