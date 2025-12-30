from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
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
        nav_categories = list(
            Category.objects.order_by("name").annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=BlogPost.Status.PUBLISHED),
                    distinct=True,
                )
            )
        )
        cache.set(cache_key, nav_categories, timeout=600)

    tag_cache_key = "nav_tags"
    nav_tags = cache.get(tag_cache_key)

    if nav_tags is None:
        qs = (
            Tag.objects.annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=BlogPost.Status.PUBLISHED),
                    distinct=True,
                )
            )
            .filter(post_count__gt=0)
            .order_by("name")
            .values("id", "name", "slug", "post_count")
        )
        nav_tags = list(qs)

        counts = [t["post_count"] for t in nav_tags]
        min_count = min(counts) if counts else 0
        max_count = max(counts) if counts else 0

        for t in nav_tags:
            if max_count == min_count:
                t["cloud_size"] = 1.0
            else:
                normalized = (t["post_count"] - min_count) / (max_count - min_count)
                t["cloud_size"] = round(0.85 + normalized * 0.75, 2)

        cache.set(tag_cache_key, nav_tags, timeout=600)

    archive_cache_key = "nav_archives"
    nav_archives = cache.get(archive_cache_key)

    if nav_archives is None:
        archive_rows = (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .annotate(month=TruncMonth("published_at"))
            .values("month")
            .annotate(post_count=Count("id"))
            .order_by("-month")
        )
        nav_archives = []
        for row in archive_rows:
            if not row["month"]:
                continue
            nav_archives.append(
                {
                    "month": row["month"],
                    "post_count": row["post_count"],
                    "key": f"{row['month'].year:04d}-{row['month'].month:02d}",
                    "url": reverse(
                        "blog:archive_detail",
                        args=[row["month"].year, row["month"].month],
                    ),
                }
            )
        cache.set(archive_cache_key, nav_archives, timeout=600)

    return {
        "nav_categories": nav_categories,
        "nav_tags": nav_tags,
        "nav_archives": nav_archives,
    }
