from django.core.management.base import BaseCommand

from blog.popularity_queue import drain_popularity_dirty
from blog.services import recalculate_popularity_scores
from blog.signals import invalidate_nav_cache


class Command(BaseCommand):
    help = (
        "Blog yazıları için popularity_score alanını yeniden hesaplar. "
        "Skor tek bir UPDATE sorgusuyla (korelasyonlu Subquery sayımları) "
        "yazılır; periyodik (cron) güvenlik ağı olarak çalıştırılabilir. "
        "--pending ile yalnızca reaction kaynaklı 'kirli' kuyruğa düşmüş "
        "yazılar işlenir (yüksek frekanslı reaction debounce'u). "
        "Email queue worker'ından (SES 14/sn) bağımsızdır."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pending",
            action="store_true",
            help=(
                "Yalnızca reaction sinyaliyle 'kirli' kuyruğa eklenmiş yazıları "
                "tek bir UPDATE ile birleştirip işle; t3.micro üzerinde DB yazma "
                "ve nav cache thrash'i azaltır."
            ),
        )

    def handle(self, *args, **options):
        verbose = options["verbosity"] > 1

        if options["pending"]:
            post_ids = drain_popularity_dirty()
            if not post_ids:
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS("Bekleyen popülerlik güncellemesi yok.")
                    )
                return

            from blog.models import BlogPost

            updated = recalculate_popularity_scores(
                BlogPost.objects.filter(pk__in=post_ids)
            )
        else:
            updated = recalculate_popularity_scores()

        # Nav popüler yazılar cache'i bayatlamasın diye geçersiz kıl (tek sefer).
        invalidate_nav_cache()
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"popularity_score güncellendi: {updated} yazı."
                )
            )
