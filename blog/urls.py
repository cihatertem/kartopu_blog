from django.urls import path
from django.views.decorators.cache import cache_page

from . import feeds, views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("rss/", cache_page(3600)(feeds.LatestPostsFeed()), name="post_feed"),
    # path("sbstck/", feeds.SubstackBulkMigrationFeed(), name="sbstck_feed"),
    path("search/", views.search_results, name="search_results"),
    path(
        "archive/<int:year>/<int:month>/", views.archive_detail, name="archive_detail"
    ),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
    path(
        "category/<slug:slug>/rss/",
        cache_page(3600)(feeds.CategoryPostsFeed()),
        name="category_feed",
    ),
    path("tag/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("preview/<slug:slug>/", views.post_preview, name="post_preview"),
    path("<slug:slug>/reaction/", views.post_reaction, name="post_reaction"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
