from blog.models import BlogPost


def published_posts_queryset(*, include_tags: bool = True):
    """Return published posts with common relations attached."""
    qs = BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).select_related(
        "author",
        "category",
    )
    if include_tags:
        qs = qs.prefetch_related("tags")
    return qs
