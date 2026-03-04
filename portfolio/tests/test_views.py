from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class FireCalculatorViewTests(TestCase):
    def test_get_context_data(self):
        url = reverse("portfolio:fire_calculator")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/fire_calculator.html")
        self.assertEqual(
            response.context["title"], "Finansal Özgürlük (F.I.R.E.) Hesaplayıcı"
        )
        self.assertEqual(response.context["active_nav"], "fire-calculator")
        self.assertIn("4% kuralı", response.context["description"])


@override_settings(SECURE_SSL_REDIRECT=False)
class SorrAnalysisViewTests(TestCase):
    def test_get_context_data(self):
        url = reverse("portfolio:sorr_analysis")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/sorr_analysis.html")
        self.assertEqual(
            response.context["title"], "Sequence of Returns Risk (SORR) Analizi"
        )
        self.assertEqual(response.context["active_nav"], "sorr-analysis")
        self.assertIn("Kötü başlangıç", response.context["description"])


@override_settings(SECURE_SSL_REDIRECT=False)
class PortfolioSimViewTests(TestCase):
    def test_get_context_data(self):
        url = reverse("portfolio:portfolio_sim")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/portfolio_sim.html")
        self.assertEqual(
            response.context["title"],
            "Reel Portföy Büyüme ve Temettü Emekliliği Simülatörü",
        )
        self.assertEqual(response.context["active_nav"], "portfolio-sim")
        self.assertIn("Bileşik Yıllık Büyüme Oranı", response.context["description"])


@override_settings(SECURE_SSL_REDIRECT=False)
class CagrSimulasyonuRedirectTests(TestCase):
    def test_redirect(self):
        url = reverse("portfolio:portfolio_sim")
        response = self.client.get("/portfoy/cagr-simulasyonu/")
        self.assertRedirects(response, url, status_code=301, target_status_code=200)
