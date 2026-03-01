import os

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import (
    social_account_added,
    social_account_updated,
)
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.signals import post_delete
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


@log_exceptions(
    exception_types=(Exception,),
    message="Error downloading and saving social avatar: %s",
)
def _download_and_save_social_avatar(sociallogin) -> None:
    account: SocialAccount = sociallogin.account
    user: User = account.user

    if user.avatar:
        return  # Only download if the user doesn't already have an avatar

    provider_id = account.provider
    social_app = account.get_provider().app

    # Helper to recursively search a dict for a key
    def _find_in_dict(d, target_key):
        if not isinstance(d, dict):
            return None
        if target_key in d:
            return d[target_key]
        for k, v in d.items():
            if isinstance(v, dict):
                result = _find_in_dict(v, target_key)
                if result:
                    return result
        return None

    # Try to get the configured field name for the avatar
    avatar_url_field = None
    if social_app and social_app.settings:
        avatar_url_field = social_app.settings.get("avatar_url_field")

    avatar_url = None
    if avatar_url_field:
        # User specified a specific key (might be nested)
        avatar_url = _find_in_dict(account.extra_data, avatar_url_field)
    else:
        # Fallback to common fields depending on the provider, or generic search
        common_fields = ["picture", "profile_image_url", "avatar_url"]
        for field in common_fields:
            result = _find_in_dict(account.extra_data, field)
            if result:
                avatar_url = result
                break

    if not avatar_url:
        return

    # Download the avatar
    response = requests.get(avatar_url, timeout=5)
    response.raise_for_status()

    # Determine a simple filename
    filename = "social_avatar.jpg"

    content_type = response.headers.get("Content-Type", "image/jpeg")

    # Save the file to the user's avatar field (this triggers resize and storage mechanisms)
    user.avatar = SimpleUploadedFile(
        filename, response.content, content_type=content_type
    )
    user.save()


@receiver(social_account_added)
def on_social_account_added(request, sociallogin, **kwargs):
    _download_and_save_social_avatar(sociallogin)


@receiver(social_account_updated)
def on_social_account_updated(request, sociallogin, **kwargs):
    _download_and_save_social_avatar(sociallogin)
