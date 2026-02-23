from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path(
        "fire-hesaplayici/", views.FireCalculatorView.as_view(), name="fire_calculator"
    ),
    path("cagr-simulasyonu/", views.PortfolioSimView.as_view(), name="portfolio_sim"),
]
