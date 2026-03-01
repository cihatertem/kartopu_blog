import os
from collections.abc import Mapping

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import (
    social_account_added,
    social_account_updated,
)
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.decorators import log_exceptions

from .models import User


@log_exceptions(
    exception_types=(OSError, NotImplementedError),
    message="Error deleting empty avatar folder",
)
def _delete_empty_folder(storage, path: str) -> None:
    folder = os.path.dirname(storage.path(path))
    if os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)


@receiver(post_delete, sender=User)
def delete_user_avatar(sender, instance: User, **kwargs) -> None:
    """
    Kullanıcı silindiğinde avatar dosyasını ve klasörünü de sil.
    """
    avatar = instance.avatar

    if not avatar or not avatar.name:
        return

    storage = avatar.storage
    avatar_name = avatar.name
    avatar.delete(save=False)  # type: ignore

    if isinstance(storage, FileSystemStorage):
        _delete_empty_folder(storage, avatar_name)


def _find_key_in_mapping(data: Mapping[str, object], target_key: str) -> str | None:
    value = data.get(target_key)
    if isinstance(value, str):
        return value

    for nested_value in data.values():
        if isinstance(nested_value, Mapping):
            result = _find_key_in_mapping(nested_value, target_key)
            if result:
                return result

    return None


def _find_value_by_path(data: Mapping[str, object], field: str) -> str | None:
    """
    Return avatar url from mapping.

    Supports:
      - direct keys (e.g. picture)
      - dot paths (e.g. data.user.avatar)
      - fallback recursive key search
    """
    if not isinstance(data, Mapping) or not field:
        return None

    if "." in field:
        current: object = data
        for part in field.split("."):
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(part)

        if isinstance(current, str):
            return current

    return _find_key_in_mapping(data, field)


def _resolve_social_app_settings(sociallogin) -> dict:
    app = getattr(sociallogin, "app", None)
    if app and getattr(app, "settings", None):
        return app.settings

    account = getattr(sociallogin, "account", None)
    if account is None:
        return {}

    try:
        provider = account.get_provider()
    except Exception:
        return {}

    provider_app = getattr(provider, "app", None)
    if provider_app and getattr(provider_app, "settings", None):
        return provider_app.settings

    return {}


def _build_sociallogin_like(account: SocialAccount):
    class _SocialLoginLike:
        def __init__(self, social_account: SocialAccount):
            self.account = social_account
            self.app = None

    return _SocialLoginLike(account)


@log_exceptions(
    exception_types=(Exception,),
    message="Error downloading and saving social avatar: %s",
)
def _download_and_save_social_avatar(sociallogin) -> None:
    account: SocialAccount = sociallogin.account
    user: User = account.user

    if user.avatar:
        return  # Only download if the user doesn't already have an avatar

    social_app_settings = _resolve_social_app_settings(sociallogin)

    # Try to get the configured field name for the avatar
    avatar_url_field = social_app_settings.get("avatar_url_field")

    avatar_url = None
    if avatar_url_field:
        avatar_url = _find_value_by_path(account.extra_data, avatar_url_field)
    else:
        # Fallback to common fields depending on the provider, or generic search
        common_fields = ["picture", "profile_image_url", "avatar_url"]
        for field in common_fields:
            result = _find_value_by_path(account.extra_data, field)
            if result:
                avatar_url = result
                break

    if not avatar_url:
        return

    # Download the avatar
    response = requests.get(
        avatar_url,
        timeout=10,
        headers={"User-Agent": "kartopu-blog-avatar-fetcher/1.0"},
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "image/jpeg")

    # Save the file to the user's avatar field (this triggers resize and storage mechanisms)
    user.avatar = SimpleUploadedFile(
        "social_avatar.jpg", response.content, content_type=content_type
    )
    user.save(update_fields=["avatar", "updated_at"])


def _download_and_save_social_avatar_for_account(account: SocialAccount) -> None:
    sociallogin_like = _build_sociallogin_like(account)
    _download_and_save_social_avatar(sociallogin_like)


@receiver(social_account_added)
def on_social_account_added(request, sociallogin, **kwargs):
    _download_and_save_social_avatar(sociallogin)


@receiver(social_account_updated)
def on_social_account_updated(request, sociallogin, **kwargs):
    _download_and_save_social_avatar(sociallogin)


@receiver(post_save, sender=SocialAccount)
def on_social_account_saved(sender, instance: SocialAccount, created: bool, **kwargs):
    """
    Ensure avatar ingestion also runs when SocialAccount is saved directly.

    Some allauth flows may skip social_account_added for first-time social signups,
    while still creating SocialAccount rows. This fallback keeps avatar ingestion
    reliable for both local and S3 storages.
    """
    if not created and instance.user.avatar:
        return

    _download_and_save_social_avatar_for_account(instance)
