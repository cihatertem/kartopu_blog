# Register your models here.
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import BlogPost, BlogPostImage, Category, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


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
    autocomplete_fields = ("author", "category")
    filter_horizontal = ("tags",)

    def public_link(self, obj: BlogPost) -> SafeString:
        # url = obj.get_absolute_url()
        # return format_html("<a href='{}' target='_blank' rel='noopener'>Aç</a>", url)
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
