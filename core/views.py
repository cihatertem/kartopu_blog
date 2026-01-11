from django.shortcuts import render
from django.utils.text import slugify

from blog.models import BlogPost, Category


# Create your views here.
def home_view(request):
    portfolio_slug = slugify("portföy")
    portfolio_category = Category.objects.filter(slug=portfolio_slug).first()
    portfolio_posts = []

    if portfolio_category:
        portfolio_posts = list(
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED,
                category=portfolio_category,
            )
            .select_related("author", "category")
            .order_by("-published_at", "-created_at")[:5]
        )

    featured_post = (
        BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED,
            is_featured=True,
        )
        .select_related("author", "category")
        .order_by("-published_at", "-created_at")
        .first()
    )

    context = {
        "active_nav": "home",
        "portfolio_category": portfolio_category,
        "portfolio_posts": portfolio_posts,
        "featured_post": featured_post,
    }

    return render(request, "core/home.html", context)


def about_view(request):
    context = {
        "active_nav": "about",
    }

    return render(request, "core/about.html", context)


def contact_view(request):
    context = {
        "active_nav": "contact",
    }

    return render(request, "core/contact.html", context)
