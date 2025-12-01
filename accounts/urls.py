from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.author_profile_view, name="author_profile"),
]
