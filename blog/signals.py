import os
import shutil

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import NAV_KEYS

from .models import BlogPost, BlogPostImage, Category, Tag


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
