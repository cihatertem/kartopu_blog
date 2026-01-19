import mimetypes

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

    def item_enclosure_url(self, item):
        return self._get_item_cover_url(item)

    def item_enclosure_length(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return item.cover_image.size  # pyright: ignore[reportAttributeAccessIssue]

    def item_enclosure_mime_type(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return self._get_item_cover_mime_type(item)

    def _get_item_cover_url(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        cover_asset = item.cover_1200  # pyright: ignore[reportAttributeAccessIssue]
        url = cover_asset.url
        if getattr(self, "request", None):
            return self.request.build_absolute_uri(url)
        return url

    def _get_item_cover_mime_type(self, item):
        cover_asset = item.cover_1200  # pyright: ignore[reportAttributeAccessIssue]
        mime_type, _ = mimetypes.guess_type(cover_asset.name)
        return mime_type or "image/webp"


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

    def item_enclosure_url(self, item):
        return self._get_item_cover_url(item)

    def item_enclosure_length(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return item.cover_image.size  # pyright: ignore[reportAttributeAccessIssue]

    def item_enclosure_mime_type(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return self._get_item_cover_mime_type(item)

    def _get_item_cover_url(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        cover_asset = item.cover_1200  # pyright: ignore[reportAttributeAccessIssue]
        url = cover_asset.url
        if getattr(self, "request", None):
            return self.request.build_absolute_uri(url)
        return url

    def _get_item_cover_mime_type(self, item):
        cover_asset = item.cover_1200  # pyright: ignore[reportAttributeAccessIssue]
        mime_type, _ = mimetypes.guess_type(cover_asset.name)
        return mime_type or "image/webp"
