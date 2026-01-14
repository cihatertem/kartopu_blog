from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, IntegerField, Q
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.translation import get_language

from blog.cache_keys import (
    NAV_ARCHIVES_KEY,
    NAV_CATEGORIES_KEY,
    NAV_POPULAR_POSTS_KEY,
    NAV_RECENT_POSTS_KEY,
    NAV_TAGS_KEY,
)
from blog.models import BlogPost, Category, Tag
from comments.models import Comment
from portfolio.models import PortfolioSnapshot

from .models import ContactMessage
from .tag_colors import get_tag_color_class

CACHE_TIMEOUT = 600  # 10 minutes


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
    nav_categories = cache.get(NAV_CATEGORIES_KEY)

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
        cache.set(NAV_CATEGORIES_KEY, nav_categories, timeout=CACHE_TIMEOUT)

    nav_tags = cache.get(NAV_TAGS_KEY)

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
            t["color_class"] = get_tag_color_class(t["slug"])

        cache.set(NAV_TAGS_KEY, nav_tags, timeout=CACHE_TIMEOUT)

    nav_archives_key = f"{NAV_ARCHIVES_KEY}:{get_language() or 'tr'}"
    nav_archives = cache.get(nav_archives_key)

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
                    "label": date_format(row["month"], "F Y"),
                    "post_count": row["post_count"],
                    "key": f"{row['month'].year:04d}-{row['month'].month:02d}",
                    "url": reverse(
                        "blog:archive_detail",
                        args=[row["month"].year, row["month"].month],
                    ),
                }
            )
            cache.set(nav_archives_key, nav_archives, timeout=CACHE_TIMEOUT)

    nav_recent_posts = cache.get(NAV_RECENT_POSTS_KEY)

    if nav_recent_posts is None:
        nav_recent_posts = list(
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .order_by("-published_at")
            .only("title", "slug")[:5]
        )
        cache.set(NAV_RECENT_POSTS_KEY, nav_recent_posts, timeout=CACHE_TIMEOUT)

    nav_popular_posts = cache.get(NAV_POPULAR_POSTS_KEY)

    if nav_popular_posts is None:
        nav_popular_posts = list(
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .annotate(
                approved_comment_count=Count(
                    "comments",
                    filter=Q(comments__status=Comment.Status.APPROVED),
                    distinct=True,
                ),
            )
            .annotate(
                popularity_score=ExpressionWrapper(
                    F("approved_comment_count") * 5 + F("view_count"),
                    output_field=IntegerField(),
                )
            )
            .order_by("-popularity_score", "-view_count", "-published_at")
            .only("title", "slug", "view_count")[:5]
        )
        cache.set(NAV_POPULAR_POSTS_KEY, nav_popular_posts, timeout=CACHE_TIMEOUT)

    featured_snapshot = (
        PortfolioSnapshot.objects.select_related("portfolio")
        .filter(is_featured=True)
        .order_by("-snapshot_date", "-created_at")
        .first()
    )

    goal_widget_snapshot = None
    if featured_snapshot:
        target_value = featured_snapshot.target_value
        total_value = featured_snapshot.total_value
        remaining_value = max(target_value - total_value, Decimal("0"))
        if target_value > 0:
            remaining_pct = (remaining_value / target_value) * Decimal("100")
        else:
            remaining_pct = Decimal("0")
        remaining_pct = max(Decimal("0"), min(remaining_pct, Decimal("100")))
        remaining_pct_display = int(
            remaining_pct.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

        formatted_target = f"{target_value:,.0f}".replace(",", ".")
        formatted_current = f"{total_value:,.0f}".replace(",", ".")
        target_pct = {
            "value": 100 - remaining_pct_display,
            "display": remaining_pct_display,
        }

        goal_widget_snapshot = {
            "name": featured_snapshot.name or featured_snapshot.portfolio.name,
            "current_value": total_value,
            "target_value": target_value,
            "current_display": f"{formatted_current} ₺",
            "target_display": f"{formatted_target} ₺",
            "remaining_pct": target_pct,
        }

    unread_contact_message_count = 0
    if request.user.is_authenticated and request.user.is_staff:
        unread_contact_message_count = ContactMessage.objects.filter(
            is_read=False,
        ).count()

    return {
        "nav_categories": nav_categories,
        "nav_tags": nav_tags,
        "nav_archives": nav_archives,
        "nav_recent_posts": nav_recent_posts,
        "nav_popular_posts": nav_popular_posts,
        "goal_widget_snapshot": goal_widget_snapshot,
        "unread_contact_message_count": unread_contact_message_count,
    }


def google_analytics_context(request):
    return {"GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID}
