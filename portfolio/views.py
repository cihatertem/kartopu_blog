from django.views.generic import TemplateView


class FireCalculatorView(TemplateView):
    template_name = "portfolio/fire_calculator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "title": "Finansal Özgürlük (F.I.R.E.) Hesaplayıcı",
                "description": "Portföyünüzün sizi ne zaman finansal olarak özgür kılacağını hesaplayın. 4% kuralı ve bileşik getiri ile F.I.R.E. yolculuğunuzu planlayın.",
                "active_nav": "fire-calculator",
            }
        )
        return context


class PortfolioSimView(TemplateView):
    template_name = "portfolio/portfolio_sim.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "title": "Reel Portföy Büyüme ve Temettü Emekliliği Simülatörü",
                "description": "Portföyünüzün enflasyondan arındırılmış gerçek büyümesini hesaplayın. Temettü verimi ve reel CAGR ile satın alma gücünüzü kaç yıl koruyabileceğinizi görün.",
                "active_nav": "portfolio-sim",
            }
        )
        return context
