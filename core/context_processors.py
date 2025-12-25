from __future__ import annotations

from django.urls import reverse

from blog.models import BlogPost, Category


def breadcrumbs(request):
    """
    Otomatik breadcrumb üretir.

    Kurallar:
    - Her zaman: Ana sayfa / ...
    - Blog list: Ana sayfa / Blog
    - Category detail: Ana sayfa / Blog / <Kategori>
    - Post detail: Ana sayfa / Blog / <Kategori> / <Post>
    """
    items: list[dict[str, str | None]] = []

    match = getattr(request, "resolver_match", None)
    if not match:
        return {"breadcrumbs": items}

    view_name = match.view_name  # örn: "blog:post_list"
    kwargs = match.kwargs or {}

    blog_url = reverse("blog:post_list")

    if view_name == "blog:post_list":
        items.append({"label": "Blog", "url": None})
        return {"breadcrumbs": items}

    if view_name == "blog:category_detail":
        items.append({"label": "Blog", "url": blog_url})

        slug = kwargs.get("slug")
        if slug:
            category = Category.objects.only("name", "slug").filter(slug=slug).first()
            if category:
                items.append({"label": category.name, "url": None})
        return {"breadcrumbs": items}

    if view_name == "blog:post_detail":
        items.append({"label": "Blog", "url": blog_url})

        slug = kwargs.get("slug")
        if slug:
            post = (
                BlogPost.objects.select_related("category")
                .only("title", "slug", "category__name", "category__slug")
                .filter(slug=slug)
                .first()
            )
            if post:
                if post.category:
                    items.append(
                        {
                            "label": post.category.name,
                            "url": post.category.get_absolute_url(),
                        }
                    )
                items.append({"label": post.title, "url": None})
        return {"breadcrumbs": items}

    # Blog dışındaki sayfalarda breadcrumb istemiyorsan boş bırak:
    return {"breadcrumbs": items}


def categories(request):
    return {"nav_categories": Category.objects.order_by("name")}
