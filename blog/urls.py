from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.blog_view, name="blog_view"),
    path("<slug:slug>/", views.post_detail, name="post_detail"),
]
