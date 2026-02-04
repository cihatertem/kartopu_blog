import mimetypes

from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.utils.text import Truncator

from core.decorators import log_exceptions
from core.imagekit import safe_file_url
from core.markdown import render_markdown

from .models import BlogPost, Category


@log_exceptions(message="Error getting cover image size")
def _safe_cover_size(image_field) -> int | None:
    return image_field.size


@log_exceptions(message="Error getting cover name")
def _get_cover_name(item) -> str | None:
    try:
        return item.cover_1200.name  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        return item.cover_image.name  # pyright: ignore[reportAttributeAccessIssue]


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
            return render_markdown(item.excerpt)  # pyright: ignore[reportAttributeAccessIssue]
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
        return _safe_cover_size(item.cover_image)

    def item_enclosure_mime_type(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return self._get_item_cover_mime_type(item)

    def _get_item_cover_url(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        cover_rendition = getattr(item, "cover_rendition", None)
        url = (
            cover_rendition["src"]
            if cover_rendition
            else safe_file_url(item.cover_image)
        )
        if not url:
            return None
        if getattr(self, "request", None):
            return self.request.build_absolute_uri(url)  # pyright: ignore[reportAttributeAccessIssue]
        return url

    def _get_item_cover_mime_type(self, item):
        cover_name = _get_cover_name(item)
        if not cover_name:
            return "image/webp"
        mime_type, _ = mimetypes.guess_type(cover_name)
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
            return render_markdown(item.excerpt)  # pyright: ignore[reportAttributeAccessIssue]
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
        return _safe_cover_size(item.cover_image)

    def item_enclosure_mime_type(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        return self._get_item_cover_mime_type(item)

    def _get_item_cover_url(self, item):
        if not item.cover_image:  # pyright: ignore[reportAttributeAccessIssue]
            return None
        cover_rendition = getattr(item, "cover_rendition", None)
        url = (
            cover_rendition["src"]
            if cover_rendition
            else safe_file_url(item.cover_image)
        )
        if not url:
            return None
        if getattr(self, "request", None):
            return self.request.build_absolute_uri(url)  # pyright: ignore[reportAttributeAccessIssue]
        return url

    def _get_item_cover_mime_type(self, item):
        cover_name = _get_cover_name(item)
        if not cover_name:
            return "image/webp"
        mime_type, _ = mimetypes.guess_type(cover_name)
        return mime_type or "image/webp"
