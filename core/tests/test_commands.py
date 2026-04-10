import os
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from core.models import SidebarWidget


class SyncSidebarWidgetsCommandTests(TestCase):
    def setUp(self):
        # Create a temporary directory for templates
        self.test_dir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.test_dir, "templates", "includes")
        os.makedirs(self.templates_dir)

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_sync_with_missing_directory(self):
        # Override BASE_DIR to a directory where templates/includes doesn't exist
        with patch.object(settings, "BASE_DIR", self.test_dir):
            shutil.rmtree(os.path.join(self.test_dir, "templates"))

            out = StringIO()
            call_command("sync_sidebar_widgets", stdout=out)
            output = out.getvalue()

            self.assertIn("Template directory does not exist", output)

    def test_sync_with_no_files(self):
        with patch.object(settings, "BASE_DIR", self.test_dir):
            out = StringIO()
            call_command("sync_sidebar_widgets", stdout=out)
            output = out.getvalue()

            self.assertIn("No sidebar widget templates found", output)

    def test_sync_creates_widgets(self):
        # Create some dummy template files
        file1_path = os.path.join(self.templates_dir, "sidebar_popular_posts.html")
        file2_path = os.path.join(self.templates_dir, "sidebar_newsletter.html")

        with open(file1_path, "w") as f:
            f.write("content")
        with open(file2_path, "w") as f:
            f.write("content")

        with patch.object(settings, "BASE_DIR", self.test_dir):
            out = StringIO()
            call_command("sync_sidebar_widgets", stdout=out)
            output = out.getvalue()

            # Check output
            self.assertIn("Created widget for sidebar_popular_posts.html", output)
            self.assertIn("Created widget for sidebar_newsletter.html", output)
            self.assertIn("Successfully synced 2 widgets (2 new)", output)

            # Check database
            self.assertEqual(SidebarWidget.objects.count(), 2)
            self.assertTrue(
                SidebarWidget.objects.filter(
                    template_name="includes/sidebar_popular_posts.html",
                    title="Popular Posts",
                ).exists()
            )
            self.assertTrue(
                SidebarWidget.objects.filter(
                    template_name="includes/sidebar_newsletter.html", title="Newsletter"
                ).exists()
            )

    def test_sync_does_not_duplicate_existing_widgets(self):
        # Create a widget that already exists
        SidebarWidget.objects.create(
            template_name="includes/sidebar_existing.html",
            title="Custom Title",
        )

        file_path = os.path.join(self.templates_dir, "sidebar_existing.html")
        with open(file_path, "w") as f:
            f.write("content")

        with patch.object(settings, "BASE_DIR", self.test_dir):
            out = StringIO()
            call_command("sync_sidebar_widgets", stdout=out)
            output = out.getvalue()

            self.assertNotIn("Created widget for", output)
            self.assertIn("Successfully synced 1 widgets (0 new)", output)

            # Check that it didn't create a new one or overwrite the title
            self.assertEqual(SidebarWidget.objects.count(), 1)
            widget = SidebarWidget.objects.get(
                template_name="includes/sidebar_existing.html"
            )
            self.assertEqual(widget.title, "Custom Title")
