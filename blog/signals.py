import os
import shutil

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import BlogPost, BlogPostImage


def _delete_storage_file(field) -> None:
    if not field:
        return
    try:
        name = getattr(field, "name", "")
        if name:
            field.storage.delete(name)
    except Exception:
        pass


def _delete_local_dir_if_exists(path: str) -> None:
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _post_media_dir(post: BlogPost) -> str:
    return os.path.join(settings.MEDIA_ROOT, "blog", post.slug)


def _post_cache_dir(post: BlogPost) -> str:
    cache_dir = getattr(settings, "IMAGEKIT_CACHEFILE_DIR", "cache")
    return os.path.join(settings.MEDIA_ROOT, cache_dir, "blog", post.slug)


@receiver(post_delete, sender=BlogPostImage)
def blogpostimage_delete_files(sender, instance: BlogPostImage, **kwargs):
    _delete_storage_file(instance.image)


@receiver(post_delete, sender=BlogPost)
def blogpost_delete_files(sender, instance: BlogPost, **kwargs):
    _delete_local_dir_if_exists(_post_cache_dir(instance))

    _delete_local_dir_if_exists(_post_media_dir(instance))
