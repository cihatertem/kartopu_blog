from django.test import TestCase

from core.apps import CoreConfig


class CoreConfigTests(TestCase):
    def test_apps_config(self):
        # Arrange & Act
        # The app config is initialized by Django, we just verify its attribute.

        # Assert
        self.assertEqual(CoreConfig.name, "core")
