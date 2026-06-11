import os
import shutil

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Value
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from blog.cache_keys import (
    BLOG_POST_DETAIL_KEY_PREFIX,
    BLOG_POST_REACTIONS_KEY_PREFIX,
    NAV_ARCHIVES_KEY,
    NAV_KEYS,
)
from core.decorators import log_exceptions

from .models import BlogPost, BlogPostImage, BlogPostReaction, Category, Tag
from .services import recalculate_popularity_score


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


@log_exceptions(message="Error deleting storage file")
def _delete_single_storage_file(path: str) -> None:
    default_storage.delete(path)


@log_exceptions(message="Error deleting storage directory")
def _delete_storage_dir_if_exists(path: str) -> None:
    if not path:
        return

    try:
        directories, files = default_storage.listdir(path)
    except Exception:
        return

    for file_name in files:
        _delete_single_storage_file(os.path.join(path, file_name))
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
    keys_to_delete = list(NAV_KEYS)
    if NAV_ARCHIVES_KEY in keys_to_delete:
        keys_to_delete.remove(NAV_ARCHIVES_KEY)
        for lang_code, _ in getattr(settings, "LANGUAGES", [("tr", "Turkish")]):
            keys_to_delete.append(f"{NAV_ARCHIVES_KEY}:{lang_code}")
    cache.delete_many(keys_to_delete)


def update_search_vector(post: BlogPost):
    if connection.vendor != "postgresql":
        return

    tags_str = " ".join(post.tags.values_list("name", flat=True).iterator())
    vector = (
        SearchVector(Value(tags_str), weight="A", config="turkish")
        + SearchVector("title", weight="B", config="turkish")
        + SearchVector("excerpt", weight="C", config="turkish")
        + SearchVector("content", weight="D", config="turkish")
    )
    BlogPost.objects.filter(pk=post.pk).update(search_vector=vector)


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def category_changed(sender, **kwargs):
    invalidate_nav_cache()


@receiver(post_save, sender=Tag)
@receiver(post_delete, sender=Tag)
def tag_changed(sender, **kwargs):
    invalidate_nav_cache()


@receiver(post_save, sender=BlogPost)
def post_changed_save(sender, instance: BlogPost, **kwargs):
    update_search_vector(instance)
    recalculate_popularity_score(instance.pk)
    cache.delete(f"{BLOG_POST_DETAIL_KEY_PREFIX}{instance.slug}")
    invalidate_nav_cache()


@receiver(post_delete, sender=BlogPost)
def post_changed_delete(sender, instance: BlogPost, **kwargs):
    cache.delete(f"{BLOG_POST_DETAIL_KEY_PREFIX}{instance.slug}")
    invalidate_nav_cache()


@receiver(m2m_changed, sender=BlogPost.tags.through)
def post_tags_changed(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        update_search_vector(instance)
        invalidate_nav_cache()


@receiver(post_save, sender=BlogPostReaction)
@receiver(post_delete, sender=BlogPostReaction)
def blogpostreaction_changed(sender, instance: BlogPostReaction, **kwargs):
    cache.delete(f"{BLOG_POST_REACTIONS_KEY_PREFIX}{instance.post_id}")
    recalculate_popularity_score(instance.post_id)
    invalidate_nav_cache()
