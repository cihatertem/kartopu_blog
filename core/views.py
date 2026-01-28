from __future__ import print_function

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from blog.models import Category
from core.helpers import (
    CAPTCHA_SESSION_KEY,
    _generate_captcha,
    captcha_is_valid,
    client_ip_key,
    get_client_ip,
)
from core.models import AboutPage
from core.services.blog import published_posts_queryset

from .forms import ContactForm

CONTACT_RATE_LIMIT = "3/m"
CONTACT_RATE_LIMIT_KEY = "ip"


# Create your views here.
def home_view(request):
    portfolio_slug = slugify("portföy")
    portfolio_category = Category.objects.filter(slug=portfolio_slug).first()
    portfolio_posts = []

    if portfolio_category:
        portfolio_posts = list(
            published_posts_queryset(include_tags=False)
            .filter(category=portfolio_category)
            .order_by("-published_at", "-created_at")[:5]
        )

    featured_post = (
        published_posts_queryset(include_tags=False)
        .filter(is_featured=True)
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
    about_page = (
        AboutPage.objects.prefetch_related("images").order_by("-updated_at").first()
    )
    context = {
        "active_nav": "about",
        "about_page": about_page,
    }

    return render(request, "core/about.html", context)


@ratelimit(
    key=client_ip_key,
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

        if not captcha_is_valid(request):
            messages.error(
                request, "Toplam alanı boş ya da hatalı. Lütfen tekrar deneyin."
            )
            return redirect("core:contact")

        request.session.pop(CAPTCHA_SESSION_KEY, None)

        if form.is_valid():
            contact_message = form.save(commit=False)

            if bool(form.cleaned_data.get("website")):
                messages.success(
                    request,
                    "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
                )
                return redirect("core:contact")

            contact_message.ip_address = get_client_ip(request)
            contact_message.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            contact_message.save()
            messages.success(
                request,
                "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
            )
            return redirect("core:contact")

        messages.error(request, "Lütfen form alanlarını kontrol edin.")

    num_one, num_two = _generate_captcha(request)

    context = {
        "active_nav": "contact",
        "form": form,
        "num1": num_one,
        "num2": num_two,
    }

    return render(request, "core/contact.html", context)
