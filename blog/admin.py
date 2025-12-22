# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import BlogPost, BlogPostImage


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 1
    ordering = ("order",)

    readonly_fields = ("thumb",)

    fields = ("thumb", "image", "alt_text", "caption", "order")

    def thumb(self, obj: BlogPostImage) -> str | SafeString:
        if not obj.pk or not obj.image:
            return "—"

        try:
            url = obj.image_600.url  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            url = obj.image.url

        return format_html(
            "<img src='{}' style='height:60px; width:auto; border-radius:6px;' loading='lazy' />",
            url,
        )

    thumb.short_description = "Önizleme"  # pyright: ignore[ reportFunctionMemberAccess]


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    inlines = [BlogPostImageInline]

    list_display = (
        "title",
        "author",
        "status",
        "public_link",
        "published_at",
        "is_featured",
        "view_count",
    )
    list_filter = ("status", "is_featured", "created_at")
    search_fields = ("title", "excerpt", "content", "slug")
    prepopulated_fields = {"slug": ("title",)}

    def public_link(self, obj: BlogPost) -> SafeString:
        url = obj.get_absolute_url()
        return format_html("<a href='{}' target='_blank' rel='noopener'>Aç</a>", url)

    public_link.short_description = "Bağlantı"  # pyright: ignore[ reportFunctionMemberAccess]
