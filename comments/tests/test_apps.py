from django.apps import apps
from django.test import TestCase

from comments.apps import CommentsConfig


class CommentsConfigTests(TestCase):
    def test_apps(self):
        self.assertEqual(CommentsConfig.name, "comments")
        self.assertEqual(apps.get_app_config("comments").name, "comments")
