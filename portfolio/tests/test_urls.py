from django.test import SimpleTestCase
from django.urls import resolve, reverse

from portfolio.views import FireCalculatorView, PortfolioSimView, SorrAnalysisView


class UrlsTestCase(SimpleTestCase):
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
