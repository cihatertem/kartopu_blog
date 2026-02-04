import os
import shutil

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import NAV_KEYS
from core.decorators import log_exceptions

from .models import BlogPost, BlogPostImage, Category, Tag


@log_exceptions(message="Error deleting storage file")
def _delete_storage_file(field) -> None:
    if not field:
        return
    name = getattr(field, "name", "")
    if name:
        field.storage.delete(name)


@log_exceptions(message="Error deleting local directory")
def _delete_local_dir_if_exists(path: str) -> None:
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


@log_exceptions(message="Error deleting storage directory")
def _delete_storage_dir_if_exists(path: str) -> None:
    if not path:
        return

    directories, files = default_storage.listdir(path)
    for file_name in files:
        default_storage.delete(os.path.join(path, file_name))
    for directory in directories:
        _delete_storage_dir_if_exists(os.path.join(path, directory))


def _post_media_dir(post: BlogPost) -> str:
    if not settings.MEDIA_ROOT:
        return ""
    return os.path.join(settings.MEDIA_ROOT, "blog", post.slug)


def _post_cache_dir(post: BlogPost) -> str:
    if not settings.MEDIA_ROOT:
        return ""
    cache_dir = getattr(settings, "IMAGEKIT_CACHEFILE_DIR", "cache")
    return os.path.join(settings.MEDIA_ROOT, cache_dir, "blog", post.slug)


def _post_cache_storage_dir(post: BlogPost) -> str:
    cache_dir = getattr(settings, "IMAGEKIT_CACHEFILE_DIR", "cache")
    return os.path.join(cache_dir, "blog", post.slug)


@receiver(post_delete, sender=BlogPostImage)
def blogpostimage_delete_files(sender, instance: BlogPostImage, **kwargs):
    _delete_storage_file(instance.image)


@receiver(post_delete, sender=BlogPost)
def blogpost_delete_files(sender, instance: BlogPost, **kwargs):
    if getattr(settings, "USE_S3", False):
        _delete_storage_dir_if_exists(_post_cache_storage_dir(instance))
    else:
        _delete_local_dir_if_exists(_post_cache_dir(instance))

    _delete_local_dir_if_exists(_post_media_dir(instance))


def invalidate_nav_cache():
    cache.delete_many(NAV_KEYS)


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def category_changed(sender, **kwargs):
    invalidate_nav_cache()


@receiver(post_save, sender=Tag)
@receiver(post_delete, sender=Tag)
def tag_changed(sender, **kwargs):
    invalidate_nav_cache()


@receiver(post_save, sender=BlogPost)
@receiver(post_delete, sender=BlogPost)
def post_changed(sender, instance: BlogPost, **kwargs):
    invalidate_nav_cache()


@receiver(m2m_changed, sender=BlogPost.tags.through)
def post_tags_changed(sender, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        invalidate_nav_cache()
