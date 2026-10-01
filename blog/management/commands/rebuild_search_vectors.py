from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q

from blog.models import BlogPost
from blog.signals import invalidate_search_cache, update_search_vector


DEFAULT_BATCH_SIZE = 100


class Command(BaseCommand):
    help = "Rebuilds full-text search vectors for published blog posts."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rebuild vectors for all published posts, including existing vectors.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Posts per transaction (default: {DEFAULT_BATCH_SIZE}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("--batch-size must be a positive integer.")
        if connection.vendor != "postgresql":
            raise CommandError("rebuild_search_vectors requires PostgreSQL.")

        published_posts = BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED
        )
        upper_pk = published_posts.order_by("-pk").values_list("pk", flat=True).first()
        total_published = published_posts.count()
        posts = (
            published_posts.filter(pk__lte=upper_pk)
            if upper_pk is not None else published_posts.none()
        )
        if not options["all"]:
            posts = posts.filter(
                Q(search_vector__isnull=True) | Q(search_vector_exact__isnull=True)
            )

        updated_count = 0
        last_pk = None
        while upper_pk is not None:
            batch_posts = posts if last_pk is None else posts.filter(pk__gt=last_pk)
            batch = list(batch_posts.order_by("pk").only("id", "status")[:batch_size])
            if not batch:
                break
            batch_updated = 0
            try:
                with transaction.atomic():
                    for post in batch:
                        batch_updated += update_search_vector(post)
                    if batch_updated:
                        transaction.on_commit(invalidate_search_cache)
            except Exception as exc:
                raise CommandError(
                    f"Rebuild failed. Updated {updated_count} posts in earlier batches. "
                    f"{exc}"
                ) from exc
            updated_count += batch_updated
            last_pk = batch[-1].pk

        skipped_count = max(0, total_published - updated_count)
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Updated {updated_count} posts; skipped {skipped_count}."
                f" Published snapshot: {total_published} posts."
            )
        )
