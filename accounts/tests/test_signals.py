import io
from unittest.mock import MagicMock, patch

import requests
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.models import User
from accounts.signals import _download_and_save_social_avatar


class SocialAvatarDownloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test_social@example.com", password="password"
        )
        self.social_app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="123",
            secret="abc",
            settings={"avatar_url_field": "custom_picture"},
        )
        self.social_account = SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="12345",
            extra_data={"custom_picture": "http://example.com/avatar.jpg"},
        )
        self.sociallogin = SocialLogin(account=self.social_account)

    def _create_valid_image(self):
        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        return file.getvalue()

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_with_configured_field(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the actual function
        _download_and_save_social_avatar(self.sociallogin)

        # Refresh user and check avatar
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertTrue("avatars/" in self.user.avatar.name)

        # Verify get was called correctly
        mock_get.assert_called_once_with("http://example.com/avatar.jpg", timeout=5)

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_fallback_field(self, mock_get):
        # Remove custom settings
        self.social_app.settings = {}
        self.social_app.save()

        # Update extra_data
        self.social_account.extra_data = {"picture": "http://example.com/fallback.jpg"}
        self.social_account.save()

        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        mock_get.assert_called_once_with("http://example.com/fallback.jpg", timeout=5)

    @patch("accounts.signals.requests.get")
    def test_download_avatar_success_nested_field(self, mock_get):
        # Remove custom settings
        self.social_app.settings = {}
        self.social_app.save()

        # Update extra_data simulating Twitter's OAuth2 response structure
        self.social_account.extra_data = {
            "data": {
                "id": "12345",
                "name": "Twitter User",
                "username": "twitteruser",
                "profile_image_url": "http://example.com/twitter_avatar.jpg",
            }
        }
        self.social_account.save()

        mock_response = MagicMock()
        mock_response.content = self._create_valid_image()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        mock_get.assert_called_once_with(
            "http://example.com/twitter_avatar.jpg", timeout=5
        )

    @patch("accounts.signals.requests.get")
    def test_download_avatar_no_url_field(self, mock_get):
        # Remove custom settings
        self.social_app.settings = {}
        self.social_app.save()

        # Update extra_data with NO avatar field
        self.social_account.extra_data = {"name": "Test User"}
        self.social_account.save()

        _download_and_save_social_avatar(self.sociallogin)

        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        mock_get.assert_not_called()

    @patch("accounts.signals.requests.get")
    def test_download_avatar_network_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        # This should NOT raise an exception due to @log_exceptions
        try:
            _download_and_save_social_avatar(self.sociallogin)
        except Exception as e:
            self.fail(f"Raised exception unexpectedly: {e}")

        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    @patch("accounts.signals.requests.get")
    def test_download_avatar_already_has_avatar(self, mock_get):
        # Give user an avatar first
        test_uploaded_file = SimpleUploadedFile(
            "existing.jpg", self._create_valid_image(), content_type="image/jpeg"
        )
        self.user.avatar = test_uploaded_file
        self.user.save()

        _download_and_save_social_avatar(self.sociallogin)

        # Should not have called requests.get since an avatar exists
        mock_get.assert_not_called()
        import io
        from unittest.mock import MagicMock, patch

        import requests
        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import TestCase
        from PIL import Image

        from accounts.models import User
        from accounts.signals import _download_and_save_social_avatar

        class SocialAvatarDownloadTests(TestCase):
            def setUp(self):
                self.user = User.objects.create_user(
                    email="test_social@example.com", password="password"
                )
                self.social_app = SocialApp.objects.create(
                    provider="google",
                    name="Google",
                    client_id="123",
                    secret="abc",
                    settings={"avatar_url_field": "custom_picture"},
                )
                self.social_account = SocialAccount.objects.create(
                    user=self.user,
                    provider="google",
                    uid="12345",
                    extra_data={"custom_picture": "http://example.com/avatar.jpg"},
                )
                self.sociallogin = SocialLogin(account=self.social_account)

            def _create_valid_image(self):
                file = io.BytesIO()
                image = Image.new("RGB", (100, 100), "white")
                image.save(file, "JPEG")
                return file.getvalue()

            @patch("accounts.signals.requests.get")
            def test_download_avatar_success_with_configured_field(self, mock_get):
                mock_response = MagicMock()
                mock_response.content = self._create_valid_image()
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                # Call the actual function
                _download_and_save_social_avatar(self.sociallogin)

                # Refresh user and check avatar
                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar)
                self.assertTrue("avatars/" in self.user.avatar.name)

                # Verify get was called correctly
                mock_get.assert_called_once_with(
                    "http://example.com/avatar.jpg", timeout=5
                )

            @patch("accounts.signals.requests.get")
            def test_download_avatar_success_fallback_field(self, mock_get):
                # Remove custom settings
                self.social_app.settings = {}
                self.social_app.save()

                # Update extra_data
                self.social_account.extra_data = {
                    "picture": "http://example.com/fallback.jpg"
                }
                self.social_account.save()

                mock_response = MagicMock()
                mock_response.content = self._create_valid_image()
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                _download_and_save_social_avatar(self.sociallogin)

                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar)
                mock_get.assert_called_once_with(
                    "http://example.com/fallback.jpg", timeout=5
                )

            @patch("accounts.signals.requests.get")
            def test_download_avatar_success_nested_field(self, mock_get):
                # Remove custom settings
                self.social_app.settings = {}
                self.social_app.save()

                # Update extra_data simulating Twitter's OAuth2 response structure
                self.social_account.extra_data = {
                    "data": {
                        "id": "12345",
                        "name": "Twitter User",
                        "username": "twitteruser",
                        "profile_image_url": "http://example.com/twitter_avatar.jpg",
                    }
                }
                self.social_account.save()

                mock_response = MagicMock()
                mock_response.content = self._create_valid_image()
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                _download_and_save_social_avatar(self.sociallogin)

                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar)
                mock_get.assert_called_once_with(
                    "http://example.com/twitter_avatar.jpg", timeout=5
                )

            @patch("accounts.signals.requests.get")
            def test_download_avatar_no_url_field(self, mock_get):
                # Remove custom settings
                self.social_app.settings = {}
                self.social_app.save()

                # Update extra_data with NO avatar field
                self.social_account.extra_data = {"name": "Test User"}
                self.social_account.save()

                _download_and_save_social_avatar(self.sociallogin)

                self.user.refresh_from_db()
                self.assertFalse(self.user.avatar)
                mock_get.assert_not_called()

            @patch("accounts.signals.requests.get")
            def test_download_avatar_network_error(self, mock_get):
                mock_get.side_effect = requests.exceptions.RequestException(
                    "Network error"
                )

                # This should NOT raise an exception due to @log_exceptions
                try:
                    _download_and_save_social_avatar(self.sociallogin)
                except Exception as e:
                    self.fail(f"Raised exception unexpectedly: {e}")

                self.user.refresh_from_db()
                self.assertFalse(self.user.avatar)

            @patch("accounts.signals.requests.get")
            def test_download_avatar_already_has_avatar(self, mock_get):
                # Give user an avatar first
                test_uploaded_file = SimpleUploadedFile(
                    "existing.jpg",
                    self._create_valid_image(),
                    content_type="image/jpeg",
                )
                self.user.avatar = test_uploaded_file
                self.user.save()

                _download_and_save_social_avatar(self.sociallogin)

                # Should not have called requests.get since an avatar exists
                mock_get.assert_not_called()
