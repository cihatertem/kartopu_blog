from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import BlogPost, Category


def post_list(request):
    qs = (
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-published_at", "-created_at")
    )

    q = (request.GET.get("q") or "").strip()

    if q:
        # Türkçe için config="turkish" (PostgreSQL default text search config)
        vector = (
            SearchVector("title", weight="A", config="turkish")
            + SearchVector("excerpt", weight="B", config="turkish")
            + SearchVector("content", weight="C", config="turkish")
        )
        query = SearchQuery(q, config="turkish")

        qs = (
            qs.annotate(rank=SearchRank(vector, query))
            .filter(rank__gt=0.0)
            .order_by("-rank", "-published_at", "-created_at")
        )

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "blog/post_list.html",
        {
            "page_obj": page_obj,
            "active_category_slug": "",
            "active_nav": "blog",
            "q": q,
        },
    )


def post_detail(request, slug):
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        # status=BlogPost.Status.PUBLISHED,
    )

    # View count (session bazlı)
    session_key = f"viewed_post_{post.pk}"
    if not request.session.get(session_key):
        BlogPost.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        request.session[session_key] = True

    context = {
        "post": post,
        "active_nav": "blog",
    }
    return render(request, "blog/post_detail.html", context)


def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug)

    qs = (
        BlogPost.objects.filter(category=category, status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "blog/category_detail.html",
        {
            "category": category,
            "page_obj": page_obj,
            "active_category_slug": category.slug,
            "active_nav": "blog",
        },
    )
