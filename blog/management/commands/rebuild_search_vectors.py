from django.core.management.base import BaseCommand
from django.db import transaction

from blog.models import BlogPost
from blog.signals import invalidate_search_cache, update_search_vector


class Command(BaseCommand):
    help = "Rebuilds full-text search vectors for published blog posts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rebuild vectors for all published posts, including existing vectors.",
        )

    def handle(self, *args, **options):
        published_posts = BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED
        ).order_by("pk")
        posts = published_posts
        if not options["all"]:
            posts = posts.filter(search_vector__isnull=True)

        total_published = published_posts.count()
        updated_count = 0
        for post in posts.iterator(chunk_size=100):
            with transaction.atomic():
                update_search_vector(post)
                updated_count += 1

        if updated_count:
            invalidate_search_cache()

        skipped_count = total_published - updated_count
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Updated {updated_count} posts; skipped {skipped_count}."
            )
        )
