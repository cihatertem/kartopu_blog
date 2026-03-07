from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        import accounts.signals  # noqa

        from allauth.socialaccount.models import SocialApp
        from django.contrib import admin
        from accounts.admin import CustomSocialAppAdmin
        from core.decorators import log_exceptions

        @log_exceptions(
            exception_types=(admin.sites.NotRegistered,),
            message="SocialApp not registered",
        )
        def _unregister_social_app():
            admin.site.unregister(SocialApp)

        _unregister_social_app()
        admin.site.register(SocialApp, CustomSocialAppAdmin)
