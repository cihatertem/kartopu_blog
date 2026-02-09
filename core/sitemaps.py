from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import BlogPost, Category, Tag


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
            # "portfolio:portfolio_view",
            "blog:post_list",
        ]

    def location(self, item: str) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
        return reverse(item)


class BlogPostSitemap(BaseSitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .order_by("-published_at")
            .only("slug", "updated_at", "published_at")
        )

    def lastmod(self, obj: BlogPost):
        return obj.updated_at or obj.published_at


class BlogCategorySitemap(BaseSitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.all().only("slug", "updated_at")

    def lastmod(self, obj: Category):
        return obj.updated_at


class BlogTagSitemap(BaseSitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Tag.objects.all().only("slug", "updated_at")

    def lastmod(self, obj: Tag):
        return obj.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "blog": BlogPostSitemap,
    "categories": BlogCategorySitemap,
    # "tags": BlogTagSitemap, # Disabled to reduce sitemap size and tags already no index meta tagged
}
