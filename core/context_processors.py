from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q
from django.urls import reverse

from blog.models import BlogPost, Category, Tag


def breadcrumbs_context(request):
    """
    Otomatik breadcrumb üretimi
    """
    breadcrumbs = []

    if request.resolver_match and request.resolver_match.app_name == "blog":
        breadcrumbs.append(
            {
                "label": "Blog",
                "url": reverse("blog:post_list"),
            }
        )

    return {"breadcrumbs": breadcrumbs}


def categories_tags_context(request):
    cache_key = "nav_categories"
    nav_categories = cache.get(cache_key)

    if nav_categories is None:
        nav_categories = list(Category.objects.order_by("name"))
        cache.set(cache_key, nav_categories, timeout=600)

    tag_cache_key = "nav_tags"
    nav_tags = cache.get(tag_cache_key)

    if nav_tags is None:
        nav_tags = list(
            Tag.objects.annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=BlogPost.Status.PUBLISHED),
                    distinct=True,
                )
            )
            .filter(post_count__gt=0)
            .order_by("name")
        )
        cache.set(tag_cache_key, nav_tags, timeout=600)

    counts = [tag.post_count for tag in nav_tags]  # pyright: ignore[reportAttributeAccessIssue]
    min_count = min(counts) if counts else 0
    max_count = max(counts) if counts else 0

    for tag in nav_tags:
        if max_count == min_count:
            tag.cloud_size = 1.0  # pyright: ignore[reportAttributeAccessIssue]
        else:
            normalized = (tag.post_count - min_count) / (max_count - min_count)  # pyright: ignore[reportAttributeAccessIssue]
            tag.cloud_size = round(0.85 + normalized * 0.75, 2)  # pyright: ignore[reportAttributeAccessIssue]

    return {"nav_categories": nav_categories, "nav_tags": nav_tags}
