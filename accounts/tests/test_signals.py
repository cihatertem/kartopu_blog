import io
from unittest.mock import MagicMock, patch

import requests
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.models import User
from accounts.signals import _delete_empty_folder, _download_and_save_social_avatar


class DeleteEmptyFolderTests(TestCase):
    def setUp(self):
        self.mock_storage = MagicMock()
        self.mock_storage.path.return_value = "/path/to/folder/file.txt"

    @patch("accounts.signals.os.path.dirname")
    @patch("accounts.signals.os.path.isdir")
    @patch("accounts.signals.os.listdir")
    @patch("accounts.signals.os.rmdir")
    def test_delete_empty_folder_success(
        self, mock_rmdir, mock_listdir, mock_isdir, mock_dirname
    ):
        mock_dirname.return_value = "/path/to/folder"
        mock_isdir.return_value = True
        mock_listdir.return_value = []

        _delete_empty_folder(self.mock_storage, "folder/file.txt")

        mock_rmdir.assert_called_once_with("/path/to/folder")

    @patch("accounts.signals.os.path.dirname")
    @patch("accounts.signals.os.path.isdir")
    @patch("accounts.signals.os.listdir")
    @patch("accounts.signals.os.rmdir")
    def test_delete_empty_folder_not_empty(
        self, mock_rmdir, mock_listdir, mock_isdir, mock_dirname
    ):
        mock_dirname.return_value = "/path/to/folder"
        mock_isdir.return_value = True
        mock_listdir.return_value = ["other_file.txt"]

        _delete_empty_folder(self.mock_storage, "folder/file.txt")

        mock_rmdir.assert_not_called()

    @patch("accounts.signals.os.path.dirname")
    @patch("accounts.signals.os.path.isdir")
    @patch("accounts.signals.os.listdir")
    @patch("accounts.signals.os.rmdir")
    def test_delete_empty_folder_not_a_dir(
        self, mock_rmdir, mock_listdir, mock_isdir, mock_dirname
    ):
        mock_dirname.return_value = "/path/to/folder"
        mock_isdir.return_value = False

        _delete_empty_folder(self.mock_storage, "folder/file.txt")

        mock_rmdir.assert_not_called()
        mock_listdir.assert_not_called()

    @patch("accounts.signals.os.path.dirname")
    @patch("accounts.signals.os.path.isdir")
    @patch("accounts.signals.os.listdir")
    @patch("accounts.signals.os.rmdir")
    def test_delete_empty_folder_oserror_caught(
        self, mock_rmdir, mock_listdir, mock_isdir, mock_dirname
    ):
        mock_dirname.return_value = "/path/to/folder"
        mock_isdir.return_value = True
        mock_listdir.return_value = []
        mock_rmdir.side_effect = OSError("Permission denied")

        with self.assertLogs("accounts.signals", level="ERROR") as cm:
            _delete_empty_folder(self.mock_storage, "folder/file.txt")

        self.assertIn("Error deleting empty avatar folder", cm.output[0])

    def test_delete_empty_folder_not_implemented_error(self):
        self.mock_storage.path.side_effect = NotImplementedError(
            "This storage doesn't support path()"
        )

        with self.assertLogs("accounts.signals", level="ERROR") as cm:
            _delete_empty_folder(self.mock_storage, "folder/file.txt")

        self.assertIn("Error deleting empty avatar folder", cm.output[0])


class SocialAvatarDownloadTests(TestCase):
    def setUp(self):

        import accounts.signals

        self.thread_patcher = patch.object(accounts.signals.threading, "Thread")
        self.mock_thread = self.thread_patcher.start()

        def mock_thread_init(target, daemon=None, *args, **kwargs):
            mock_obj = MagicMock()
            mock_obj.start = lambda: target()
            return mock_obj

        self.mock_thread.side_effect = mock_thread_init

        self.user = User.objects.create_user(
            email="test_social@example.com", password="password"
        )
        self.social_account = SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="12345",
            extra_data={"name": "Test User"},
        )
        self.sociallogin = SocialLogin(account=self.social_account)

    def tearDown(self):
        self.thread_patcher.stop()
        super().tearDown()

    def _create_valid_image(self):
        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        return file.getvalue()

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_with_sociallogin_app_setting(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_get.return_value = mock_response

        self.sociallogin.app = SocialApp(
            provider="google",
            name="Google",
            client_id="123",
            secret="abc",
            settings={"avatar_url_field": "custom_picture"},
        )
        self.social_account.extra_data = {
            "custom_picture": "http://example.com/avatar.jpg"
        }

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertIn("avatars/", self.user.avatar.name)
        mock_get.assert_called_once_with(
            "http://example.com/avatar.jpg",
            timeout=10,
            headers={"User-Agent": "kartopu-blog-avatar-fetcher/1.0"},
        )

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_fallback_field_without_app(self, mock_get):
        self.social_account.extra_data = {"picture": "http://example.com/fallback.jpg"}

        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_get.return_value = mock_response

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        mock_get.assert_called_once_with(
            "http://example.com/fallback.jpg",
            timeout=10,
            headers={"User-Agent": "kartopu-blog-avatar-fetcher/1.0"},
        )

    @patch("accounts.signals.requests.get")
    def test_download_avatar_triggered_on_social_account_create(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_get.return_value = mock_response

        user = User.objects.create_user(
            email="signal-create@example.com", password="password"
        )
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid="new-social-uid",
            extra_data={"picture": "http://example.com/new.jpg"},
        )

        user.refresh_from_db()
        self.assertTrue(user.avatar)
        mock_get.assert_called_once_with(
            "http://example.com/new.jpg",
            timeout=10,
            headers={"User-Agent": "kartopu-blog-avatar-fetcher/1.0"},
        )

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_nested_dot_path(self, mock_get):
        self.social_account.extra_data = {
            "data": {"user": {"avatar": "http://example.com/twitter_avatar.jpg"}}
        }

        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_get.return_value = mock_response

        self.sociallogin.app = SocialApp(
            provider="google",
            name="Google",
            client_id="123",
            secret="abc",
            settings={"avatar_url_field": "data.user.avatar"},
        )

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        mock_get.assert_called_once_with(
            "http://example.com/twitter_avatar.jpg",
            timeout=10,
            headers={"User-Agent": "kartopu-blog-avatar-fetcher/1.0"},
        )

    @patch("accounts.signals.requests.get")
    def test_download_avatar_no_url_field(self, mock_get):
        self.social_account.extra_data = {"name": "Test User"}

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        mock_get.assert_not_called()

    @patch("accounts.signals.requests.get")
    def test_download_avatar_network_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    @patch("accounts.signals.requests.get")
    def test_download_avatar_already_has_avatar(self, mock_get):
        self.user.avatar = SimpleUploadedFile(
            "existing.jpg", self._create_valid_image(), content_type="image/jpeg"
        )
        self.user.save()

        _download_and_save_social_avatar(self.sociallogin)

        mock_get.assert_not_called()
