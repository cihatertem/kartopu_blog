from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("search/", views.search_results, name="search_results"),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
    path("tag/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("preview/<slug:slug>/", views.post_preview, name="post_preview"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
