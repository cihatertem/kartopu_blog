from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        import accounts.signals  # noqa

        from allauth.socialaccount.models import SocialApp
        from django.contrib import admin
        from accounts.admin import CustomSocialAppAdmin

        try:
            admin.site.unregister(SocialApp)
        except admin.sites.NotRegistered:
            pass
        admin.site.register(SocialApp, CustomSocialAppAdmin)
