import io
from unittest.mock import MagicMock, patch

import requests
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.models import User
from accounts.signals import (
    AVATAR_DOWNLOAD_TIMEOUT,
    _delete_empty_folder,
    _download_and_save_social_avatar,
)


class DeleteEmptyFolderTests(TestCase):
    def setUp(self):
        self.mock_storage = MagicMock()

    def test_delete_empty_folder_empty_path(self):
        _delete_empty_folder(self.mock_storage, "")
        _delete_empty_folder(self.mock_storage, None)

        self.mock_storage.listdir.assert_not_called()
        self.mock_storage.delete.assert_not_called()

    def test_delete_empty_folder_success(self):
        self.mock_storage.listdir.return_value = ([], [])

        _delete_empty_folder(self.mock_storage, "avatars/empty_folder")

        self.mock_storage.listdir.assert_called_once_with("avatars/empty_folder")
        self.mock_storage.delete.assert_called_once_with("avatars/empty_folder")

    def test_delete_empty_folder_has_files(self):
        self.mock_storage.listdir.return_value = ([], ["file.jpg"])

        _delete_empty_folder(self.mock_storage, "avatars/not_empty")

        self.mock_storage.listdir.assert_called_once_with("avatars/not_empty")
        self.mock_storage.delete.assert_not_called()

    def test_delete_empty_folder_has_dirs(self):
        self.mock_storage.listdir.return_value = (["subdir"], [])

        _delete_empty_folder(self.mock_storage, "avatars/not_empty")

        self.mock_storage.listdir.assert_called_once_with("avatars/not_empty")
        self.mock_storage.delete.assert_not_called()

    def test_delete_empty_folder_oserror_caught(self):
        self.mock_storage.listdir.side_effect = OSError("Permission denied")

        _delete_empty_folder(self.mock_storage, "avatars/folder")

        self.mock_storage.delete.assert_not_called()

    def test_delete_empty_folder_not_implemented_error(self):
        self.mock_storage.listdir.side_effect = NotImplementedError(
            "This storage doesn't support listdir()"
        )

        _delete_empty_folder(self.mock_storage, "avatars/folder")

        self.mock_storage.delete.assert_not_called()


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
            timeout=AVATAR_DOWNLOAD_TIMEOUT,
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
            timeout=AVATAR_DOWNLOAD_TIMEOUT,
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
            timeout=AVATAR_DOWNLOAD_TIMEOUT,
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
            timeout=AVATAR_DOWNLOAD_TIMEOUT,
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

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_allauth_signals_trigger_download(self, mock_download):
        from allauth.socialaccount.signals import (
            social_account_added,
            social_account_updated,
        )

        social_account_added.send(
            sender=SocialAccount, request=None, sociallogin=self.sociallogin
        )
        self.assertEqual(mock_download.call_count, 1)

        social_account_updated.send(
            sender=SocialAccount, request=None, sociallogin=self.sociallogin
        )
        self.assertEqual(mock_download.call_count, 2)


class UserSignalTests(TestCase):
    def test_delete_user_avatar_signal(self):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        user = User.objects.create_user(email="delete-me@example.com")
        import io

        from PIL import Image

        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        user.avatar.save("to_be_deleted.jpg", ContentFile(file.getvalue()), save=True)
        avatar_name = user.avatar.name

        self.assertTrue(default_storage.exists(avatar_name))

        user.delete()

        self.assertFalse(default_storage.exists(avatar_name))


class BuildSocialLoginLikeTests(TestCase):
    def test_build_sociallogin_like(self):
        user = User.objects.create_user(
            email="test_social_like@example.com", password="password"
        )
        account = SocialAccount.objects.create(user=user, provider="google", uid="123")

        from accounts.signals import _build_sociallogin_like

        login = _build_sociallogin_like(account)

        self.assertIsInstance(login, SocialLogin)
        self.assertEqual(login.user, user)
        self.assertEqual(login.account, account)
