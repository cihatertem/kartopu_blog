from django.core.management.base import BaseCommand

from blog.services import recalculate_popularity_scores
from blog.signals import invalidate_nav_cache


class Command(BaseCommand):
    help = (
        "Tüm blog yazıları için popularity_score alanını yeniden hesaplar. "
        "Skor tek bir UPDATE sorgusuyla (korelasyonlu Subquery sayımları) "
        "yazılır; periyodik (cron) güvenlik ağı olarak çalıştırılabilir. "
        "Email queue worker'ından (SES 14/sn) bağımsızdır."
    )

    def handle(self, *args, **options):
        updated = recalculate_popularity_scores()
        # Nav popüler yazılar cache'i bayatlamasın diye geçersiz kıl.
        invalidate_nav_cache()
        if options["verbosity"] > 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"popularity_score güncellendi: {updated} yazı."
                )
            )
