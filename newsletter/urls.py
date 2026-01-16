from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("subscribe/", views.subscribe_request, name="subscribe_request"),
    path("unsubscribe/", views.unsubscribe_request, name="unsubscribe_request"),
    path("confirm/<str:token>/", views.confirm_subscription, name="confirm"),
]
