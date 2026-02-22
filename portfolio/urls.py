from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("fire-calc/", views.FireCalculatorView.as_view(), name="fire_calculator"),
]
