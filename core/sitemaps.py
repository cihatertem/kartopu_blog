from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.urls import reverse

from blog.cache_keys import SITEMAP_BLOG_POSTS_KEY, SITEMAP_CATEGORIES_KEY
from blog.models import BlogPost, Category

# Sitemap item listeleri saatlik cache'lenir; crawl başına tam tablo taramasını
# önler. URL seviyesindeki cache_page miss olsa bile DB yükü düşük kalır.
SITEMAP_ITEMS_CACHE_TIMEOUT = 60 * 60  # 1 saat


class BaseSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"


class StaticViewSitemap(BaseSitemap):
    priority = 0.7

    def items(self) -> list[str]:
        return [
            "core:home",
            "core:about",
            "core:contact",
            "blog:post_list",
            "portfolio:fire_calculator",
            "portfolio:portfolio_sim",
        ]

    def location(self, item: str) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
        return reverse(item)


class BlogPostSitemap(BaseSitemap):
    priority = 0.9

    def items(self):
        cached_items = cache.get(SITEMAP_BLOG_POSTS_KEY)
        if cached_items is None:
            cached_items = list(
                BlogPost.objects.filter(
                    status=BlogPost.Status.PUBLISHED,
                    published_at__isnull=False,
                )
                .order_by("-published_at")
                .only("slug", "updated_at", "published_at")
            )
            cache.set(
                SITEMAP_BLOG_POSTS_KEY,
                cached_items,
                timeout=SITEMAP_ITEMS_CACHE_TIMEOUT,
            )
        return cached_items

    def lastmod(self, obj: BlogPost):
        return obj.updated_at or obj.published_at


class BlogCategorySitemap(BaseSitemap):
    priority = 0.6

    def items(self):
        cached_items = cache.get(SITEMAP_CATEGORIES_KEY)
        if cached_items is None:
            cached_items = list(Category.objects.all().only("slug", "updated_at"))
            cache.set(
                SITEMAP_CATEGORIES_KEY,
                cached_items,
                timeout=SITEMAP_ITEMS_CACHE_TIMEOUT,
            )
        return cached_items

    def lastmod(self, obj: Category):
        return obj.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "blog": BlogPostSitemap,
    "categories": BlogCategorySitemap,
}
