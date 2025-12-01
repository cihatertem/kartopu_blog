from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("", views.comments_view, name="comments_view"),
]
