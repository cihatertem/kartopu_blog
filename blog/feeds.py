from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.utils.text import Truncator

from .models import BlogPost, Category


class LatestPostsFeed(Feed):
    title = "Kartopu Blog - Tüm Yazılar"
    link = "/blog/"
    description = "Kartopu Blog'daki en yeni yazılar."

    def items(self):
        return (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .select_related("category")
            .order_by("-published_at")[:20]
        )

    def item_title(self, item):
        return item.title  # pyright: ignore[reportAttributeAccessIssue]

    def item_description(self, item):  # pyright: ignore[reportIncompatibleMethodOverride]
        if item.excerpt:  # pyright: ignore[reportAttributeAccessIssue]
            return item.excerpt  # pyright: ignore[reportAttributeAccessIssue]
            return Truncator(item.content).words(40)  # pyright: ignore[reportAttributeAccessIssue]

    def item_link(self, item):
        return item.get_absolute_url()  # pyright: ignore[reportAttributeAccessIssue]

    def item_pubdate(self, item):
        return item.published_at


class CategoryPostsFeed(Feed):
    def get_object(self, request, slug):  # pyright: ignore[reportIncompatibleMethodOverride]
        return get_object_or_404(Category, slug=slug)

    def title(self, obj):
        return f"Kartopu Blog - {obj.name} Yazıları"

    def link(self, obj):
        return obj.get_absolute_url()

    def description(self, obj):
        return obj.description or "Kartopu Blog'daki en yeni kategori yazıları."

    def items(self, obj):
        return (
            obj.posts.filter(
                status=BlogPost.Status.PUBLISHED,
                published_at__isnull=False,
            )
            .select_related("category")
            .order_by("-published_at")[:20]
        )

    def item_title(self, item):
        return item.title  # pyright: ignore[reportAttributeAccessIssue]

    def item_description(self, item):  # pyright: ignore[reportIncompatibleMethodOverride]
        if item.excerpt:  # pyright: ignore[reportAttributeAccessIssue]
            return item.excerpt  # pyright: ignore[reportAttributeAccessIssue]
            return Truncator(item.content).words(40)  # pyright: ignore[reportAttributeAccessIssue]

    def item_link(self, item):
        return item.get_absolute_url()  # pyright: ignore[reportAttributeAccessIssue]

    def item_pubdate(self, item):
        return item.published_at
