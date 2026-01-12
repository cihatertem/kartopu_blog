from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import index, sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from accounts import views as account_views
from core.sitemaps import sitemaps

urlpatterns = [
    path("admin/", admin.site.urls),
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
    path("portfolio/", include("portfolio.urls", namespace="portfolio")),
    path("blog/", include("blog.urls", namespace="blog")),
    path("authors/", include("accounts.urls", namespace="accounts")),
    path("comments/", include("comments.urls", namespace="comments")),
    path(
        "sitemap.xml",
        index,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.index",
    ),
    path(
        "sitemap-<section>.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
