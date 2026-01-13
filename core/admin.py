from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import AboutPage, AboutPageImage, ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_spam", "created_at")
    list_filter = ("is_spam", "created_at")
    search_fields = ("name", "email", "subject", "message")


class AboutPageImageInline(admin.TabularInline):
    model = AboutPageImage
    extra = 1
    ordering = ("order",)
    readonly_fields = ("thumb",)
    fields = ("thumb", "image", "alt_text", "caption", "order")

    class Media:
        css = {"all": ("css/admin.css",)}

    def thumb(self, obj: AboutPageImage) -> str | SafeString:
        if not obj.pk or not obj.image:
            return "—"

        try:
            url = obj.image_600.url  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            url = obj.image.url

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
