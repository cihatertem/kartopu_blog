from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .models import BlogPost, Category


def post_list(request):
    qs = (
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, 10)  # sayfa başına 10 yazı
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.order_by("name")

    return render(
        request,
        "blog/post_list.html",
        {
            "page_obj": page_obj,
            "categories": categories,  # navbar/sidebar için şimdiden
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
    }
    return render(request, "blog/post_detail.html", context)


def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug)

    posts = (
        BlogPost.objects.filter(category=category, status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-published_at", "-created_at")
    )

    return render(
        request,
        "blog/category_detail.html",
        {
            "category": category,
            "posts": posts,
        },
    )
