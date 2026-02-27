from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .decorators import log_exceptions
from .models import (
    AboutPage,
    AboutPageImage,
    ContactMessage,
    PageSEO,
    SidebarWidget,
    SiteSettings,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "is_comments_enabled",
        "is_newsletter_enabled",
        "is_contact_enabled",
        "updated_at",
    )
    fieldsets = (
        (
            "Genel Ayarlar",
            {
                "fields": (
                    "is_comments_enabled",
                    "is_newsletter_enabled",
                    "is_contact_enabled",
                )
            },
        ),
        (
            "Varsayılan SEO Ayarları",
            {
                "fields": (
                    "default_meta_title",
                    "default_meta_description",
                    "default_meta_image",
                ),
                "description": "Buradaki ayarlar, spesifik bir SEO tanımı (blog yazısı, sayfa vb.) bulunamadığında kullanılır.",
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PageSEO)
class PageSEOAdmin(admin.ModelAdmin):
    list_display = ("path", "title", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("path", "title", "description")
    list_editable = ("is_active",)

    fieldsets = (
        (None, {"fields": ("path", "is_active")}),
        ("SEO Bilgileri", {"fields": ("title", "description", "image", "image_alt")}),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "is_spam", "created_at")
    list_filter = ("is_read", "is_spam", "created_at")
    search_fields = ("name", "email", "subject", "message")
    actions = (
        "mark_as_read",
        "mark_as_unread",
        "mark_as_spam",
        "mark_as_not_spam",
    )

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    mark_as_read.short_description = "Seçili mesajları okundu olarak işaretle"  # pyright: ignore[reportFunctionMemberAccess]

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)

    mark_as_unread.short_description = "Seçili mesajları okunmadı olarak işaretle"  # pyright: ignore[reportFunctionMemberAccess]

    def mark_as_spam(self, request, queryset):
        queryset.update(is_spam=True)

    mark_as_spam.short_description = "Seçili mesajları spam olarak işaretle"  # pyright: ignore[reportFunctionMemberAccess]

    def mark_as_not_spam(self, request, queryset):
        queryset.update(is_spam=False)

    mark_as_not_spam.short_description = "Seçili mesajları spam değil olarak işaretle"  # pyright: ignore[reportFunctionMemberAccess]


class AboutPageImageInline(admin.TabularInline):
    model = AboutPageImage
    extra = 1
    ordering = ("order",)
    readonly_fields = ("thumb",)
    fields = ("thumb", "image", "alt_text", "caption", "order")

    class Media:
        css = {"all": ("css/admin.css",)}

    @log_exceptions(message="Error resolving about page thumb rendition")
    def _get_rendition_url(self, obj: AboutPageImage) -> str | None:
        return obj.image_600.url  # pyright: ignore[reportAttributeAccessIssue]

    @log_exceptions(message="Error rendering about page thumb")
    def thumb(self, obj: AboutPageImage) -> str | SafeString:
        if not obj.pk or not obj.image:
            return "—"

        url = self._get_rendition_url(obj) or obj.image.url

        return format_html(
            "<img src='{}' class='admin-thumb' loading='lazy' />",
            url,
        )

    thumb.short_description = "Önizleme"  # pyright: ignore[ reportFunctionMemberAccess]


@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):
    inlines = (AboutPageImageInline,)

    list_display = ("title", "public_link", "updated_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "content",
                )
            },
        ),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    def has_add_permission(self, request) -> bool:
        if AboutPage.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def public_link(self, obj: AboutPage) -> SafeString:
        url = reverse("core:about")
        return format_html(
            "<a href='{}' target='_blank' rel='noopener'>Sayfayı Gör</a>",
            url,
        )

    public_link.short_description = "Bağlantı"  # pyright: ignore[ reportFunctionMemberAccess]


@admin.register(SidebarWidget)
class SidebarWidgetAdmin(admin.ModelAdmin):
    list_display = ("title", "template_name", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order",)

    def get_queryset(self, request):
        self.sync_widgets()
        return super().get_queryset(request)

    def sync_widgets(self):
        import os

        from django.conf import settings

        template_dir = os.path.join(settings.BASE_DIR, "templates", "includes")
        if not os.path.exists(template_dir):
            return

        files = [
            f
            for f in os.listdir(template_dir)
            if f.startswith("sidebar_") and f.endswith(".html")
        ]

        for file in files:
            template_path = f"includes/{file}"
            # Create default title from filename
            # e.g. sidebar_popular_posts.html -> Popular Posts
            default_title = (
                file.replace("sidebar_", "")
                .replace(".html", "")
                .replace("_", " ")
                .title()
            )
            SidebarWidget.objects.get_or_create(
                template_name=template_path,
                defaults={"title": default_title},
            )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # Allow deleting if the template file no longer exists
        if obj:
            import os

            from django.conf import settings

            template_path = os.path.join(
                settings.BASE_DIR, "templates", obj.template_name
            )
            if not os.path.exists(template_path):
                return True
        return False
