from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from blog.models import BlogPost, Category

from .forms import ContactForm

CONTACT_RATE_LIMIT = "2/m"
CONTACT_RATE_LIMIT_KEY = "ip"


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


@ratelimit(
    key=CONTACT_RATE_LIMIT_KEY,
    rate=CONTACT_RATE_LIMIT,
    block=False,
    method=["POST"],
)
@require_http_methods(["GET", "POST"])
def contact_view(request):
    form = ContactForm(request.POST or None)

    if request.method == "POST":
        if getattr(request, "limited", False):
            messages.error(
                request,
                "Çok fazla istek gönderdiniz. Lütfen biraz sonra tekrar deneyin.",
            )
            return redirect("core:contact")

        if form.is_valid():
            contact_message = form.save(commit=False)

            if bool(form.cleaned_data.get("website")):
                messages.success(
                    request,
                    "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
                )
                return redirect("core:contact")

            contact_message.ip_address = request.META.get("REMOTE_ADDR")
            contact_message.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            contact_message.save()
            messages.success(
                request,
                "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
            )
            return redirect("core:contact")

        messages.error(request, "Lütfen form alanlarını kontrol edin.")

    context = {
        "active_nav": "contact",
        "form": form,
    }

    return render(request, "core/contact.html", context)
