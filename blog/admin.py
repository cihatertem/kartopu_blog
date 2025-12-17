# Register your models here.
from django.contrib import admin

from .models import BlogPost, BlogPostImage


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 1
    ordering = ("order",)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "status",
        "published_at",
        "is_featured",
        "view_count",
    )
    list_filter = ("status", "is_featured", "created_at")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [BlogPostImageInline]
