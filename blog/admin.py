from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db.models import Case, F, Value, When
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from core.decorators import log_exceptions
from newsletter.models import BlogPostNotification
from newsletter.services import send_post_published_email

from .models import BlogPost, BlogPostImage, Category, Tag

User = get_user_model()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 1
    ordering = ("order",)

    readonly_fields = ("thumb",)

    fields = ("thumb", "image", "alt_text", "caption", "order")

    class Media:
        css = {"all": ("css/admin.css",)}

    @log_exceptions(message="Error resolving admin thumb rendition")
    def _get_rendition_url(self, obj: BlogPostImage) -> str | None:
        return obj.image_600.url  # pyright: ignore[reportAttributeAccessIssue]

    @log_exceptions(message="Error rendering admin thumb")
    def thumb(self, obj: BlogPostImage) -> str | SafeString:
        if not obj.pk or not obj.image:
            return "—"

        url = self._get_rendition_url(obj) or obj.image.url

        return format_html(
            "<img src='{}' class='admin-thumb' loading='lazy' />",
            url,
        )

    thumb.short_description = "Önizleme"  # pyright: ignore[ reportFunctionMemberAccess]


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    inlines = (BlogPostImageInline,)

    list_display = (
        "title",
        "author",
        "category",
        "status",
        "public_link",
        "published_at",
        "is_featured",
        "view_count",
    )
    list_filter = ("status", "category", "tags", "is_featured", "created_at")
    search_fields = ("title", "excerpt", "content", "category__name", "slug")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = (
        "category",
        "portfolio_snapshots",
        "portfolio_comparisons",
        "cashflow_snapshots",
        "cashflow_comparisons",
        "salary_savings_snapshots",
        "dividend_snapshots",
        "dividend_comparisons",
        "tags",
    )
    ordering = ("-published_at", "-created_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "author",
                    "category",
                    "portfolio_snapshots",
                    "portfolio_comparisons",
                    "cashflow_snapshots",
                    "cashflow_comparisons",
                    "salary_savings_snapshots",
                    "dividend_snapshots",
                    "dividend_comparisons",
                    "cover_image",
                    "excerpt",
                    "content",
                    "tags",
                )
            },
        ),
        (
            "Yayın Ayarları",
            {"fields": ("status", "published_at", "is_featured")},
        ),
        ("SEO", {"fields": ("meta_title", "meta_description", "canonical_url")}),
        ("İstatistik", {"fields": ("view_count",), "classes": ("collapse",)}),
    )

    actions = (
        "publish_posts",
        "draft_posts",
        "archive_posts",
        "resend_newsletter_notifications",
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "author":
            qs = User.objects.all()

            qs = qs.filter(is_staff=True)
            qs = qs.filter(socialaccount__isnull=True)
            qs = qs.distinct()

            kwargs["queryset"] = qs

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if request.user.is_authenticated and request.user.is_staff:
            initial.setdefault("author", request.user.pk)  # pyright: ignore[reportArgumentType]
        return initial

    @admin.action(description="Seçili yazıları yayımla")
    def publish_posts(self, request, queryset):
        queryset.update(
            status=BlogPost.Status.PUBLISHED,
            published_at=Case(
                When(published_at__isnull=True, then=Value(timezone.now())),
                default=F("published_at"),
            ),
        )

    @admin.action(description="Seçili yazıları taslak yap")
    def draft_posts(self, request, queryset):
        queryset.update(status=BlogPost.Status.DRAFT)

    @admin.action(description="Seçili yazıları arşivle")
    def archive_posts(self, request, queryset):
        queryset.update(status=BlogPost.Status.ARCHIVED)

    @admin.action(description="Seçili yazılar için newsletter bildirimi gönder")
    def resend_newsletter_notifications(self, request, queryset):
        sent_count = 0
        skipped_count = 0
        for post in queryset:
            if post.status != BlogPost.Status.PUBLISHED or not post.published_at:
                skipped_count += 1
                continue
            send_post_published_email(post)
            BlogPostNotification.objects.update_or_create(
                post=post,
                defaults={"sent_at": timezone.now()},
            )
            sent_count += 1

        if sent_count:
            self.message_user(
                request,
                f"{sent_count} yazı için newsletter bildirimi tekrar gönderildi.",
            )
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} yazı yayınlanmadığı için atlandı.",
                level=messages.WARNING,
            )

    def public_link(self, obj: BlogPost) -> SafeString:
        if obj.status == BlogPost.Status.PUBLISHED:
            url = obj.get_absolute_url()
            label = "Yayını Gör"
        else:
            url = reverse("blog:post_preview", kwargs={"slug": obj.slug})
            label = "Önizleme"

        return format_html(
            "<a href='{}' target='_blank' rel='noopener'>{}</a>",
            url,
            label,
        )

    public_link.short_description = "Bağlantı"  # pyright: ignore[ reportFunctionMemberAccess]
