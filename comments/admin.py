from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("body", "author__email", "author__first_name", "author__last_name")
    autocomplete_fields = ("post", "author")
    readonly_fields = (
        "ip_address",
        "user_agent",
        "social_provider",
        "created_at",
        "updated_at",
    )

    actions = ("approve_comments", "reject_comments", "mark_spam")

    @admin.action(description="Seçili yorumları onayla")
    def approve_comments(self, request, queryset):
        queryset.update(status=Comment.Status.APPROVED)

    @admin.action(description="Seçili yorumları reddet")
    def reject_comments(self, request, queryset):
        queryset.update(status=Comment.Status.REJECTED)

    @admin.action(description="Seçili yorumları spam olarak işaretle")
    def mark_spam(self, request, queryset):
        queryset.update(status=Comment.Status.SPAM)
