from django.contrib import admin, messages
from django.utils import timezone

# Register your models here.
from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioSnapshot,
    PortfolioSnapshotItem,
    PortfolioTransaction,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "asset_type", "currency", "current_price")
    search_fields = ("name", "symbol")
    list_filter = ("asset_type", "currency")
    readonly_fields = ("price_updated_at",)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "target_value")
    search_fields = ("name", "owner__email")
    list_filter = ("owner",)

    actions = ["create_monthly_snapshot"]

    @admin.action(description="Aylık snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        created = 0
        for p in queryset:
            PortfolioSnapshot.create_snapshot(
                portfolio=p,
                period=PortfolioSnapshot.Period.MONTHLY,
                snapshot_date=timezone.now().date(),
            )
            created += 1
        self.message_user(
            request, f"{created} adet snapshot oluşturuldu.", level=messages.SUCCESS
        )

    @admin.action(description="Aylık snapshot oluştur")
    def create_yearly_snapshot(self, request, queryset):
        created = 0
        for p in queryset:
            PortfolioSnapshot.create_snapshot(
                portfolio=p,
                period=PortfolioSnapshot.Period.YEARLY,
                snapshot_date=timezone.now().date(),
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
