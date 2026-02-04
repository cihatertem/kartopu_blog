import os

from django.core.files.storage import FileSystemStorage
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

    # Hiç avatar yüklememişse
    if not avatar or not avatar.name:
        return

    # Dosyayı sil (storage üzerinden, OverWriteAvatarStorage dahil)
    storage = avatar.storage
    avatar_name = avatar.name
    avatar.delete(save=False)  # type: ignore

    # Klasörü boşsa klasörü de kaldır (yalnızca yerel dosya sistemi)
    if isinstance(storage, FileSystemStorage):
        _delete_empty_folder(storage, avatar_name)
