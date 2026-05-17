from django.test import SimpleTestCase
from django.urls import resolve, reverse
from django.views.generic import RedirectView

from portfolio.views import (
    BudgetTrackerView,
    FireCalculatorView,
    PortfolioSimView,
    SorrAnalysisView,
)


class UrlsTestCase(SimpleTestCase):
    def test_budget_tracker_url_resolves(self):
        url = reverse("portfolio:budget_tracker")
        self.assertEqual(url, "/portfoy/butce-takibi/")
        self.assertEqual(resolve(url).func.view_class, BudgetTrackerView)

    def test_fire_calculator_url_resolves(self):
        url = reverse("portfolio:fire_calculator")
        self.assertEqual(url, "/portfoy/fire-hesaplayici/")
        self.assertEqual(resolve(url).func.view_class, FireCalculatorView)

    def test_portfolio_sim_url_resolves(self):
        url = reverse("portfolio:portfolio_sim")
        self.assertEqual(url, "/portfoy/portfoy-simulasyonu/")
        self.assertEqual(resolve(url).func.view_class, PortfolioSimView)

    def test_sorr_analysis_url_resolves(self):
        url = reverse("portfolio:sorr_analysis")
        self.assertEqual(url, "/portfoy/sorr-analizi/")
        self.assertEqual(resolve(url).func.view_class, SorrAnalysisView)

    def test_cagr_simulasyonu_url_resolves(self):
        url = "/portfoy/cagr-simulasyonu/"
        match = resolve(url)
        self.assertEqual(match.func.view_class, RedirectView)
        self.assertEqual(
            match.func.view_initkwargs["pattern_name"], "portfolio:portfolio_sim"
        )
        self.assertEqual(match.func.view_initkwargs["permanent"], True)
        self.assertEqual(match.func.view_initkwargs["query_string"], True)
