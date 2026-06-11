from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from blog.signals import invalidate_nav_cache
from core.context_processors import (
    _get_nav_archives,
    _get_nav_categories,
    _get_nav_popular_posts,
    _get_nav_portfolio_posts,
    _get_nav_recent_posts,
    _get_nav_tags,
)


class Command(BaseCommand):
    help = (
        "Nav (sidebar) cache anahtarlarını önceden ısıtır: categories, tags, "
        "archives, recent, popular ve portfolio. TTL dolduğunda eşzamanlı "
        "isteklerin ağır Count/JOIN sorgularını aynı anda çalıştırmasını "
        "(thundering herd) önlemek için periyodik (cron) çalıştırılabilir. "
        "Email queue worker'ından (SES 14/sn) bağımsızdır; yalnızca okuma "
        "sorguları + Redis SET yapar."
    )

    def handle(self, *args, **options):
        # Bayat değerlerin üstüne yazabilmek için önce nav anahtarlarını
        # geçersiz kıl; ardından getter'lar cache miss'te taze değeri hesaplayıp
        # tek Redis SET ile yazar. Stampede kilidi recompute'u tek thread'e sabitler.
        invalidate_nav_cache()

        # Dilden bağımsız anahtarlar bir kez ısıtılır.
        _get_nav_categories()
        _get_nav_tags()
        _get_nav_recent_posts()
        _get_nav_popular_posts()
        _get_nav_portfolio_posts()

        # Archives anahtarı dile özeldir (`nav_archives:<lang>`); her dil için ısıt.
        languages = getattr(settings, "LANGUAGES", [("tr", "Turkish")])
        for lang_code, _ in languages:
            with translation.override(lang_code):
                _get_nav_archives()

        if options["verbosity"] > 1:
            self.stdout.write(
                self.style.SUCCESS(
                    "Nav cache ısıtıldı: categories, tags, recent, popular, "
                    f"portfolio + archives ({len(languages)} dil)."
                )
            )
