from __future__ import annotations

from django.urls import reverse

from blog.models import Category


def breadcrumbs(request):
    """
    Otomatik breadcrumb üretimi
    """
    breadcrumbs = []

    # Blog ile ilgili tüm sayfalar
    if request.resolver_match and request.resolver_match.app_name == "blog":
        breadcrumbs.append(
            {
                "label": "Blog",
                "url": reverse("blog:post_list"),
            }
        )

    return {"breadcrumbs": breadcrumbs}


def categories(request):
    return {"nav_categories": Category.objects.order_by("name")}
