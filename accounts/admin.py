from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User

# Register your models here.


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "full_name",
        "is_staff",
        "is_active",
        "last_login",
        "updated_at",
        "created_at",
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
    )
    list_filter = (
        "is_staff",
        "is_active",
        "created_at",
        "updated_at",
        "last_login",
    )
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "bio",
                    "website",
                    "twitter",
                    "github",
                    "linkedin",
                    "instagram",
                    "youtube",
                    "avatar",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    actions = [
        "make_superuser",
        "remove_superuser",
        "make_staff",
        "remove_staff",
        "make_active",
        "make_passive",
    ]

    @admin.action(description=_("Make selected users superusers"))
    def make_superuser(self, request, queryset):
        updated = queryset.update(is_superuser=True, is_staff=True)
        self.message_user(
            request,
            _("%(count)d users successfully marked as superuser.") % {"count": updated},
        )

    @admin.action(description=_("Remove superuser status from selected users"))
    def remove_superuser(self, request, queryset):
        updated = queryset.update(is_superuser=False)
        self.message_user(
            request,
            _("%(count)d users successfully removed from superuser status.")
            % {"count": updated},
        )

    @admin.action(description=_("Make selected users staff"))
    def make_staff(self, request, queryset):
        updated = queryset.update(is_staff=True)
        self.message_user(
            request,
            _("%(count)d users successfully marked as staff.") % {"count": updated},
        )

    @admin.action(description=_("Remove staff status from selected users"))
    def remove_staff(self, request, queryset):
        updated = queryset.update(is_staff=False, is_superuser=False)
        self.message_user(
            request,
            _("%(count)d users successfully removed from staff status.")
            % {"count": updated},
        )

    @admin.action(description=_("Make selected users active"))
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _("%(count)d users successfully marked as active.") % {"count": updated},
        )

    @admin.action(description=_("Make selected users passive"))
    def make_passive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            _("%(count)d users successfully marked as passive.") % {"count": updated},
        )
