from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "portfolio"

urlpatterns = [
    path(
        "fire-hesaplayici/", views.FireCalculatorView.as_view(), name="fire_calculator"
    ),
    path(
        "portfoy-simulasyonu/", views.PortfolioSimView.as_view(), name="portfolio_sim"
    ),
    path("sorr-analizi/", views.SorrAnalysisView.as_view(), name="sorr_analysis"),
    path(
        "cagr-simulasyonu/",
        RedirectView.as_view(
            pattern_name="portfolio:portfolio_sim",
            permanent=True,
            query_string=True,
        ),
    ),
]
