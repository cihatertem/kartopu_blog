from __future__ import annotations

import random
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.translation import get_language

from blog.cache_keys import (
    GOAL_WIDGET_KEY,
    NAV_ARCHIVES_KEY,
    NAV_CATEGORIES_KEY,
    NAV_POPULAR_POSTS_KEY,
    NAV_PORTFOLIO_POSTS_KEY,
    NAV_RECENT_POSTS_KEY,
    NAV_TAGS_KEY,
    SIDEBAR_WIDGETS_KEY,
    STAFF_PENDING_NOTIFICATIONS_KEY,
)
from blog.models import BlogPost, Category, Tag
from comments.models import Comment
from portfolio.models import PortfolioSnapshot

from .models import ContactMessage, SidebarWidget, SiteSettings
from .tag_colors import get_tag_color_class

CACHE_TIMEOUT = 600  # 10 minutes
# TTL'lere eklenen rastgele sapma; tüm nav anahtarlarının aynı anda expire olup
# senkron (thundering herd) recompute spike'ı yaratmasını engeller.
CACHE_TIMEOUT_JITTER = 60  # 0-60 sn
# Cache miss anında yalnızca tek thread'in ağır sorguyu çalıştırmasını sağlayan
# stampede kilidinin TTL'i (saniye). t3.micro'da eşzamanlı recompute'u önler.
STAMPEDE_LOCK_TIMEOUT = 10
# Kilidi kaybeden thread'in taze değeri beklerken harcayacağı azami süre (saniye).
STAMPEDE_LOCK_WAIT = 3.0
STAMPEDE_POLL_INTERVAL = 0.1
STAFF_PENDING_CACHE_TIMEOUT = 300  # 5 minutes
GOAL_WIDGET_EMPTY_CACHE_VALUE = "__empty_goal_widget_snapshot__"
GOAL_WIDGET_CACHE_MISS_VALUE = "__missing_goal_widget_snapshot__"


def _cache_timeout_with_jitter() -> int:
    """
    TTL'e rastgele sapma ekler; nav anahtarlarının senkron expire olmasını
    önleyerek periyodik recompute spike'ini dağıtır.
    """
    return CACHE_TIMEOUT + random.randint(0, CACHE_TIMEOUT_JITTER)


def _get_or_set_with_stampede_lock(
    cache_key: str, cached_data, compute: Callable[[], object]
):
    """
    Cache stampede (thundering herd) korumalı okuma.

    TTL dolduğunda eşzamanlı isteklerin aynı ağir `Count`/`JOIN` sorgularini
    tekrar tekrar çalıştırmasını engeller: `cache.add` (Redis'te atomik SETNX)
    ile yalnızca tek thread recompute eder, digerleri kisa süre taze değeri
    bekler. Kazanan zamaninda bitiremezse bekleyen thread fallback olarak
    kendisi hesaplar (kalici blok olmaz).
    """
    if cached_data is not None:
        value = cached_data.get(cache_key)
    else:
        value = cache.get(cache_key)
    if value is not None:
        return value

    lock_key = f"{cache_key}:lock"
    got_lock = cache.add(lock_key, 1, STAMPEDE_LOCK_TIMEOUT)
    if not got_lock:
        deadline = time.monotonic() + STAMPEDE_LOCK_WAIT
        while time.monotonic() < deadline:
            time.sleep(STAMPEDE_POLL_INTERVAL)
            value = cache.get(cache_key)
            if value is not None:
                return value
        # Kazanan thread zamaninda bitiremedi; fallback olarak kendimiz hesaplariz.

    try:
        value = compute()
        cache.set(cache_key, value, timeout=_cache_timeout_with_jitter())
    finally:
        if got_lock:
            cache.delete(lock_key)
    return value


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


def _get_nav_categories(cached_data=None):
    def compute():
        qs = (
            Category.objects.annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=BlogPost.Status.PUBLISHED),
                )
            )
            .order_by("name")
            .values("name", "slug", "post_count")
        )
        nav_categories = list(qs)
        for c in nav_categories:
            c["get_absolute_url"] = reverse(
                "blog:category_detail", kwargs={"slug": c["slug"]}
            )
        return nav_categories

    return _get_or_set_with_stampede_lock(NAV_CATEGORIES_KEY, cached_data, compute)


def _calculate_tag_cloud_sizes(nav_tags):
    if not nav_tags:
        return

    min_count = nav_tags[0]["post_count"]
    max_count = min_count
    for t in nav_tags:
        c = t["post_count"]
        if c < min_count:
            min_count = c
        elif c > max_count:
            max_count = c

    if max_count == min_count:
        for t in nav_tags:
            t["cloud_size"] = 1.0
            t["cloud_size_class"] = "tag-cloud__item--size-2"
            t["color_class"] = get_tag_color_class(t["slug"])
    else:
        diff_inv = 1.0 / (max_count - min_count)
        for t in nav_tags:
            normalized = (t["post_count"] - min_count) * diff_inv
            t["cloud_size"] = round(0.85 + normalized * 0.75, 2)
            size_level = min(6, max(1, int(round(normalized * 5.0)) + 1))
            t["cloud_size_class"] = f"tag-cloud__item--size-{size_level}"
            t["color_class"] = get_tag_color_class(t["slug"])


def _get_nav_tags(cached_data=None):
    def compute():
        qs = (
            Tag.objects.annotate(
                post_count=Count(
                    "posts",
                    filter=Q(posts__status=BlogPost.Status.PUBLISHED),
                )
            )
            .filter(post_count__gt=0)
            .order_by("name")
            .values("id", "name", "slug", "post_count")
        )
        nav_tags = list(qs)
        for t in nav_tags:
            t["get_absolute_url"] = reverse("blog:tag_detail", args=[t["slug"]])

        _calculate_tag_cloud_sizes(nav_tags)
        return nav_tags

    return _get_or_set_with_stampede_lock(NAV_TAGS_KEY, cached_data, compute)


def _get_nav_archives(cached_data=None):
    nav_archives_key = f"{NAV_ARCHIVES_KEY}:{get_language() or 'tr'}"

    def compute():
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
        return nav_archives

    return _get_or_set_with_stampede_lock(nav_archives_key, cached_data, compute)


def _get_nav_recent_posts(cached_data=None):
    def compute():
        qs = (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .order_by("-published_at")
            .only("title", "slug", "published_at", "cover_image")[:5]
        )
        nav_recent_posts = []
        for post in qs:
            nav_recent_posts.append(
                {
                    "title": post.title,
                    "slug": post.slug,
                    "published_at": post.published_at,
                    "get_absolute_url": post.get_absolute_url(),
                    "cover_thumb_rendition": post.cover_thumb_rendition,
                    "cover_image": bool(post.cover_image),
                }
            )
        return nav_recent_posts

    return _get_or_set_with_stampede_lock(NAV_RECENT_POSTS_KEY, cached_data, compute)


def _get_nav_popular_posts(cached_data=None):
    def compute():
        # Popülerlik skoru `BlogPost.popularity_score` alanında denormalize
        # tutulur (sinyallerle güncellenir). Böylece her cache miss'te iki
        # `distinct` JOIN agregasyonu çalıştırmak yerine salt okuma yapılır.
        qs = (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .order_by("-popularity_score", "-view_count", "-published_at")
            .only("title", "slug", "view_count", "published_at", "cover_image")[:5]
        )
        nav_popular_posts = []
        for post in qs:
            nav_popular_posts.append(
                {
                    "title": post.title,
                    "slug": post.slug,
                    "published_at": post.published_at,
                    "get_absolute_url": post.get_absolute_url(),
                    "cover_thumb_rendition": post.cover_thumb_rendition,
                    "cover_image": bool(post.cover_image),
                }
            )
        return nav_popular_posts

    return _get_or_set_with_stampede_lock(NAV_POPULAR_POSTS_KEY, cached_data, compute)


def _get_nav_portfolio_posts(cached_data=None):
    def compute():
        qs = (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
                category__slug="portfoy",
            )
            .order_by("-published_at")
            .only("title", "slug", "published_at", "cover_image")[:5]
        )
        nav_portfolio_posts = []
        for post in qs:
            nav_portfolio_posts.append(
                {
                    "title": post.title,
                    "slug": post.slug,
                    "published_at": post.published_at,
                    "get_absolute_url": post.get_absolute_url(),
                    "cover_thumb_rendition": post.cover_thumb_rendition,
                    "cover_image": bool(post.cover_image),
                }
            )
        return nav_portfolio_posts

    return _get_or_set_with_stampede_lock(
        NAV_PORTFOLIO_POSTS_KEY, cached_data, compute
    )


def _get_goal_widget_snapshot(cached_data=None):
    if cached_data is not None:
        goal_widget_snapshot = cached_data.get(
            GOAL_WIDGET_KEY, GOAL_WIDGET_CACHE_MISS_VALUE
        )
    else:
        goal_widget_snapshot = cache.get(GOAL_WIDGET_KEY, GOAL_WIDGET_CACHE_MISS_VALUE)

    if goal_widget_snapshot != GOAL_WIDGET_CACHE_MISS_VALUE:
        if goal_widget_snapshot == GOAL_WIDGET_EMPTY_CACHE_VALUE:
            return None
        return goal_widget_snapshot

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
        achieved_pct = 100 - remaining_pct_display
        fill_pct = achieved_pct
        if total_value > 0 and fill_pct == 0:
            fill_pct = 1
        target_pct = {
            "value": achieved_pct,
            "display": remaining_pct_display,
            "fill_class": f"goal-widget__fill--{fill_pct}",
        }

        goal_widget_snapshot = {
            "name": featured_snapshot.name or featured_snapshot.portfolio.name,
            "current_value": total_value,
            "target_value": target_value,
            "current_display": f"{formatted_current} ₺",
            "target_display": f"{formatted_target} ₺",
            "remaining_pct": target_pct,
        }

    cache_value = (
        goal_widget_snapshot
        if goal_widget_snapshot is not None
        else GOAL_WIDGET_EMPTY_CACHE_VALUE
    )
    cache.set(GOAL_WIDGET_KEY, cache_value, timeout=CACHE_TIMEOUT)
    return goal_widget_snapshot


def _get_has_pending_messages_or_comments(request, cached_data=None):
    if not (request.user.is_authenticated and request.user.is_staff):
        return False

    cache_key = STAFF_PENDING_NOTIFICATIONS_KEY.format(user_id=request.user.id)
    if cached_data is not None:
        has_pending = cached_data.get(cache_key)
    else:
        has_pending = cache.get(cache_key)

    if has_pending is None:
        has_unread_messages = ContactMessage.objects.filter(is_read=False).exists()
        if has_unread_messages:
            has_pending = True
        else:
            has_pending = Comment.objects.filter(status=Comment.Status.PENDING).exists()
        cache.set(cache_key, has_pending, timeout=STAFF_PENDING_CACHE_TIMEOUT)

    return has_pending


def categories_tags_context(request):
    language = get_language() or "tr"
    nav_archives_key = f"{NAV_ARCHIVES_KEY}:{language}"

    keys = [
        NAV_CATEGORIES_KEY,
        NAV_TAGS_KEY,
        nav_archives_key,
        NAV_RECENT_POSTS_KEY,
        NAV_POPULAR_POSTS_KEY,
        NAV_PORTFOLIO_POSTS_KEY,
        GOAL_WIDGET_KEY,
    ]

    if request.user.is_authenticated and request.user.is_staff:
        staff_key = STAFF_PENDING_NOTIFICATIONS_KEY.format(user_id=request.user.id)
        keys.append(staff_key)
    else:
        staff_key = None

    cached_data = cache.get_many(keys)

    return {
        "nav_categories": _get_nav_categories(cached_data),
        "nav_tags": _get_nav_tags(cached_data),
        "nav_archives": _get_nav_archives(cached_data),
        "nav_recent_posts": _get_nav_recent_posts(cached_data),
        "nav_popular_posts": _get_nav_popular_posts(cached_data),
        "nav_portfolio_posts": _get_nav_portfolio_posts(cached_data),
        "goal_widget_snapshot": _get_goal_widget_snapshot(cached_data),
        "has_pending_messages_or_comments": _get_has_pending_messages_or_comments(
            request, cached_data
        ),
    }


def google_analytics_context(request):
    return {"GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID}


def site_metadata_context(request):
    base_url = settings.SITE_BASE_URL.rstrip("/")
    return {
        "site_name": settings.SITE_NAME,
        "site_base_url": base_url,
        "site_social_links": [
            "https://x.com/KartopuMoney",
            "https://www.youtube.com/channel/UCn4Vlw6WLaTjq1vh0OIk8lQ",
        ],
    }


def site_settings_context(request):
    return {
        "site_settings": SiteSettings.get_settings(),
    }


def sidebar_widgets_context(request):
    sidebar_widgets = cache.get(SIDEBAR_WIDGETS_KEY)
    if sidebar_widgets is None:
        sidebar_widgets = list(
            SidebarWidget.objects.filter(is_active=True)
            .order_by("order")
            .values("template_name")
        )
        cache.set(SIDEBAR_WIDGETS_KEY, sidebar_widgets, timeout=3600)
    return {"sidebar_widgets": sidebar_widgets}
