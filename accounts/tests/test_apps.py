from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.test import TestCase

from accounts.apps import AccountsConfig


class AccountsConfigTests(TestCase):
    def setUp(self):
        self.expected_app_name = "accounts"
        self.app_config = apps.get_app_config(self.expected_app_name)

    def test_apps(self):
        self.assertEqual(AccountsConfig.name, self.expected_app_name)
        self.assertEqual(self.app_config.name, self.expected_app_name)

    @patch("django.contrib.admin.site.register")
    @patch("django.contrib.admin.site.unregister")
    @patch("core.decorators.logging.getLogger")
    def test_apps_ready_unregister_exception_handling(
        self, mock_get_logger, mock_unregister, mock_register
    ):
        mock_logger = mock_get_logger.return_value
        mock_unregister.side_effect = admin.sites.NotRegistered(
            "SocialApp not registered"
        )

        self.app_config.ready()

        mock_logger.error.assert_called_with("SocialApp not registered")
