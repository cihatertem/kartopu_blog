import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import index, sitemap
from django.urls import include, path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView, TemplateView

from accounts import views as account_views
from core.sitemaps import sitemaps

SITEMAP_CACHE_SECONDS = 60 * 60  # 1 hour

urlpatterns = [
    path(os.getenv("ADMIN_ADDRESS") or "admin/", admin.site.urls),
    path(
        "accounts/login/",
        account_views.disabled_account_view,
        name="account_login_disabled",
    ),
    path(
        "accounts/signup/",
        account_views.disabled_account_view,
        name="account_signup_disabled",
    ),
    path(
        "accounts/email/",
        account_views.disabled_account_view,
        name="account_email_disabled",
    ),
    path("accounts/", include("allauth.urls")),
    path("", include("core.urls", namespace="core")),
    path("portfoy/", include("portfolio.urls", namespace="portfolio")),
    path(
        "portfolio/<path:resource>",
        RedirectView.as_view(url="/portfoy/%(resource)s", permanent=True),
    ),
    path("blog/", include("blog.urls", namespace="blog")),
    path("newsletter/", include("newsletter.urls", namespace="newsletter")),
    path("authors/", include("accounts.urls", namespace="accounts")),
    path("comments/", include("comments.urls", namespace="comments")),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
]

urlpatterns += [
    path(
        "sitemap.xml",
        cache_page(SITEMAP_CACHE_SECONDS)(index),
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.index",
    ),
    path(
        "sitemap-<section>.xml",
        cache_page(SITEMAP_CACHE_SECONDS)(sitemap),
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
