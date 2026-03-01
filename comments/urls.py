from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("post/<uuid:post_id>/", views.post_comment, name="post_comment"),
    path(
        "moderate/<uuid:comment_id>/", views.moderate_comment, name="moderate_comment"
    ),
]
