from django.views.generic import TemplateView


class FireCalculatorView(TemplateView):
    template_name = "portfolio/fire_calculator.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "title": "Finansal Özgürlük (F.I.R.E.) Hesaplayıcı",
                "description": (
                    "Portföyünüzün sizi ne zaman finansal olarak özgür kılacağını hesaplayın."
                    " 4% kuralı ve bileşik getiri ile F.I.R.E. yolculuğunuzu planlayın.</br>"
                    "<strong>Not:</strong> <a href='https://kartopu.money/blog/finansal-ozgurluk-hesaplayicisi-yayinda/' target='_blank'>Hesaplayıcıya dair blog yazımız.</a>"
                ),
                "active_nav": "fire-calculator",
            }
        )
        return context


class SorrAnalysisView(TemplateView):
    template_name = "portfolio/sorr_analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "title": "Sequence of Returns Risk (SORR) Analizi",
                "description": (
                    "Emeklilik portföyünüzün ilk yıllarındaki piyasa dalgalanmalarının "
                    "portföy ömrüne etkisini simüle edin. 'Kötü başlangıç' senaryolarının "
                    "uzun vadeli planlarınıza etkisini görün."
                ),
                "active_nav": "sorr-analysis",
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
                "description": (
                    "Portföyünüzün enflasyondan arındırılmış gerçek büyümesini hesaplayın. "
                    "Temettü verimi ve reel CAGR"
                    '<span class="tooltip">'
                    '<span class="tooltip-icon">i</span>'
                    '<span class="tooltip-text">'
                    "Bileşik Yıllık Büyüme Oranı (Compound Annual Growth Rate). "
                    "Bir yatırımın belirli bir dönem boyunca her yıl ortalama ne kadar büyüdüğünü gösteren bir ölçüttür."
                    "</span></span> ile satın alma gücünüzü kaç yıl koruyabileceğinizi görün."
                ),
                "active_nav": "portfolio-sim",
            }
        )
        return context
