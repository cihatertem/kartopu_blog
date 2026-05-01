import os

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import SidebarWidget


class Command(BaseCommand):
    help = "Syncs sidebar widgets with template files"

    def handle(self, *args, **options):
        template_dir = os.path.join(settings.BASE_DIR, "templates", "includes")
        if not os.path.exists(template_dir):
            self.stdout.write(
                self.style.WARNING(f"Template directory does not exist: {template_dir}")
            )
            return

        files = [
            f
            for f in os.listdir(template_dir)
            if f.startswith("sidebar_") and f.endswith(".html")
        ]

        if not files:
            self.stdout.write(self.style.WARNING("No sidebar widget templates found."))
            return

        existing_widgets = set(
            SidebarWidget.objects.values_list("template_name", flat=True)
        )

        widgets_to_create = []
        created_count = 0

        for file in files:
            template_path = f"includes/{file}"

            if template_path not in existing_widgets:
                # Create default title from filename
                # e.g. sidebar_popular_posts.html -> Popular Posts
                default_title = (
                    file.replace("sidebar_", "")
                    .replace(".html", "")
                    .replace("_", " ")
                    .title()
                )

                widgets_to_create.append(
                    SidebarWidget(
                        template_name=template_path,
                        title=default_title,
                    )
                )
                self.stdout.write(self.style.SUCCESS(f"Created widget for {file}"))

        if widgets_to_create:
            SidebarWidget.objects.bulk_create(widgets_to_create)
            created_count = len(widgets_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully synced {len(files)} widgets ({created_count} new)."
            )
        )
