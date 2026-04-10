import sys
from unittest.mock import patch

from django.test import SimpleTestCase

import manage


class ManagePyTest(SimpleTestCase):
    @patch("os.environ.setdefault")
    @patch("django.core.management.execute_from_command_line")
    def test_main_executes_command_line(self, mock_execute, mock_setdefault):
        """Test that manage.py main() executes the command line and sets environment variables."""
        original_argv = sys.argv
        sys.argv = ["manage.py", "check"]

        try:
            manage.main()
            mock_setdefault.assert_any_call("DJANGO_SETTINGS_MODULE", "config.settings")
            mock_execute.assert_called_once_with(["manage.py", "check"])
        finally:
            sys.argv = original_argv

    @patch.dict("sys.modules", {"django.core.management": None})
    def test_main_raises_import_error(self):
        """Test that an ImportError is raised when Django is not installed."""
        with self.assertRaisesRegex(ImportError, "Couldn't import Django"):
            manage.main()
