from django.apps import AppConfig


class CommentsConfig(AppConfig):
    name = "comments"

    def ready(self) -> None:
        from . import signals  # noqa: F401
