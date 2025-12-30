from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils import timezone

# Register your models here.
from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioSnapshot,
    PortfolioSnapshotItem,
    PortfolioTransaction,
)

User = get_user_model()


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "asset_type", "currency", "current_price")
    search_fields = ("name", "symbol")
    list_filter = ("asset_type", "currency")
    readonly_fields = ("price_updated_at",)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "target_value")
    search_fields = ("name", "owner__email")
    list_filter = ("owner",)

    actions = ("create_monthly_snapshot", "create_yearly_snapshot")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            qs = User.objects.all()

            qs = qs.filter(is_staff=True)
            qs = qs.filter(socialaccount__isnull=True)
            qs = qs.distinct()

            kwargs["queryset"] = qs

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if request.user.is_authenticated:
            initial.setdefault("owner", request.user.pk)  # pyright: ignore[reportArgumentType]
        return initial

    @admin.action(description="Aylık snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        created = 0
        for p in queryset:
            PortfolioSnapshot.create_snapshot(
                portfolio=p,
                period=PortfolioSnapshot.Period.MONTHLY,
                snapshot_date=timezone.now().date(),  # pyright: ignore[reportArgumentType]
            )
            created += 1
        self.message_user(
            request, f"{created} adet snapshot oluşturuldu.", level=messages.SUCCESS
        )

    @admin.action(description="Yıllık snapshot oluştur")
    def create_yearly_snapshot(self, request, queryset):
        created = 0
        for p in queryset:
            PortfolioSnapshot.create_snapshot(
                portfolio=p,
                period=PortfolioSnapshot.Period.YEARLY,
                snapshot_date=timezone.now().date(),  # pyright: ignore[reportArgumentType]
            )
            created += 1
        self.message_user(
            request, f"{created} adet snapshot oluşturuldu.", level=messages.SUCCESS
        )


@admin.register(PortfolioTransaction)
class PortfolioTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "portfolio",
        "asset",
        "transaction_type",
        "trade_date",
        "quantity",
        "price_per_unit",
    )
    list_filter = ("transaction_type", "trade_date")
    search_fields = ("portfolio__name", "asset__name", "asset__symbol")


class PortfolioSnapshotItemInline(admin.TabularInline):
    model = PortfolioSnapshotItem
    extra = 0
    readonly_fields = (
        "asset",
        "quantity",
        "average_cost",
        "cost_basis",
        "current_price",
        "market_value",
        "allocation_pct",
        "gain_loss",
        "gain_loss_pct",
    )
    can_delete = False


@admin.register(PortfolioSnapshot)
class PortfolioSnapshotAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "period", "snapshot_date", "total_value")
    list_filter = ("period", "snapshot_date")
    readonly_fields = ("total_value", "total_cost", "target_value", "total_return_pct")
    inlines = (PortfolioSnapshotItemInline,)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=obj.portfolio,
            period=obj.period,
            snapshot_date=obj.snapshot_date,
        )
        obj.pk = snapshot.pk
