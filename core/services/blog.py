from blog.models import BlogPost


PUBLISHED_POST_LIST_FIELDS = (
    "id",
    "created_at",
    "updated_at",
    "author_id",
    "category_id",
    "title",
    "slug",
    "excerpt",
    "status",
    "published_at",
    "cover_image",
    "view_count",
    "author__id",
    "author__email",
    "author__first_name",
    "author__last_name",
    "author__avatar",
    "category__id",
    "category__name",
    "category__slug",
)


def published_posts_queryset(*, include_tags: bool = True):
    """Return published posts with common relations attached."""
    qs = (
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
        .select_related(
            "author",
            "category",
        )
        .only(*PUBLISHED_POST_LIST_FIELDS)
    )
    if include_tags:
        qs = qs.prefetch_related("tags")
    return qs
