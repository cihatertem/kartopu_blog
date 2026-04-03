import os
from unittest import TestCase
from unittest.mock import mock_open, patch

from config.settings import get_swarm_secret_for_psg


class TestGetSwarmSecretForPsg(TestCase):
    def test_default_value_when_env_not_set(self):
        """Returns the default value if the environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_swarm_secret_for_psg("NON_EXISTENT_KEY", default="my_default")
            self.assertEqual(result, "my_default")

    def test_empty_default_when_env_not_set(self):
        """Returns empty string if the environment variable is not set and no default provided."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_swarm_secret_for_psg("NON_EXISTENT_KEY")
            self.assertEqual(result, "")

    def test_env_value_returned_directly(self):
        """Returns the environment variable value directly if it's not a file path."""
        with patch.dict(os.environ, {"MY_KEY": "my_secret_value"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "my_secret_value")

    def test_env_value_stripped_of_newline(self):
        """Returns the environment variable value stripped of trailing newline."""
        with patch.dict(os.environ, {"MY_KEY": "my_secret_value\n"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "my_secret_value")

    @patch("os.path.isfile")
    @patch("builtins.open", new_callable=mock_open, read_data="file_secret_value\n")
    def test_file_content_returned(self, mock_file, mock_isfile):
        """Returns the content of the file if the environment variable is a file path."""
        mock_isfile.return_value = True
        with patch.dict(os.environ, {"MY_KEY": "/fake/path/to/secret"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "file_secret_value")
            mock_isfile.assert_called_once_with("/fake/path/to/secret")
            mock_file.assert_called_once_with("/fake/path/to/secret")

    @patch("os.path.isfile")
    @patch("builtins.open", new_callable=mock_open, read_data="file_secret_value")
    def test_file_content_returned_without_newline_stripping(
        self, mock_file, mock_isfile
    ):
        """Returns the content of the file without trailing newlines stripped if there are none."""
        mock_isfile.return_value = True
        with patch.dict(os.environ, {"MY_KEY": "/fake/path/to/secret_no_newline"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "file_secret_value")
            mock_isfile.assert_called_once_with("/fake/path/to/secret_no_newline")
            mock_file.assert_called_once_with("/fake/path/to/secret_no_newline")

    @patch("os.path.isfile")
    @patch(
        "builtins.open", new_callable=mock_open, read_data="first_line\nsecond_line\n"
    )
    def test_multiline_file_content_returns_first_line(self, mock_file, mock_isfile):
        """Returns only the first line of the file if the environment variable is a file path."""
        mock_isfile.return_value = True
        with patch.dict(os.environ, {"MY_KEY": "/fake/path/to/multiline_secret"}):
            result = get_swarm_secret_for_psg("MY_KEY")
            self.assertEqual(result, "first_line")
            mock_isfile.assert_called_once_with("/fake/path/to/multiline_secret")
            mock_file.assert_called_once_with("/fake/path/to/multiline_secret")
