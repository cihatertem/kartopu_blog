from django.test import TestCase

from core.apps import CoreConfig


class CoreConfigTests(TestCase):
    def test_apps_config(self):
        self.assertEqual(CoreConfig.name, "core")
