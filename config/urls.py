from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("portfolio/", include("portfolio.urls", namespace="portfolio")),
    path("blog/", include("blog.urls", namespace="blog")),
    path("authors/", include("accounts.urls", namespace="accounts")),
    path("comments/", include("comments.urls", namespace="comments")),
]
