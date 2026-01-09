from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils import timezone

# Register your models here.
from portfolio.models import (
    Asset,
    CashFlow,
    CashFlowComparison,
    CashFlowEntry,
    CashFlowSnapshot,
    CashFlowSnapshotItem,
    Dividend,
    DividendComparison,
    DividendPayment,
    DividendSnapshot,
    DividendSnapshotAssetItem,
    DividendSnapshotPaymentItem,
    Portfolio,
    PortfolioComparison,
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
    list_display = ("name", "owner", "currency", "target_value", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("owner", "created_at")
    inlines = ()

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
        if request.user.is_authenticated and request.user.is_staff:
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
        "portfolio_list",
        "asset",
        "transaction_type",
        "trade_date",
        "quantity",
        "price_per_unit",
    )
    list_filter = ("portfolios", "transaction_type", "trade_date")
    search_fields = ("portfolios__name", "asset__name", "asset__symbol")
    autocomplete_fields = ("portfolios",)

    @admin.display(description="Portföyler")
    def portfolio_list(self, obj):
        return ", ".join(obj.portfolios.values_list("name", flat=True).order_by("name"))


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
    list_display = (
        "name",
        "portfolio",
        "period",
        "snapshot_date",
        "total_value",
        "is_featured",
    )
    list_filter = ("period", "snapshot_date", "is_featured")
    readonly_fields = ("total_value", "total_cost", "target_value", "total_return_pct")
    search_fields = ("name", "slug", "portfolio__name", "portfolio__owner__email")
    list_select_related = ("portfolio", "portfolio__owner")
    inlines = (PortfolioSnapshotItemInline,)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=obj.portfolio,
            period=obj.period,
            snapshot_date=obj.snapshot_date,
            name=obj.name,
        )
        obj.pk = snapshot.pk
        obj.name = snapshot.name
        obj.total_value = snapshot.total_value
        obj.total_cost = snapshot.total_cost
        obj.target_value = snapshot.target_value
        obj.total_return_pct = snapshot.total_return_pct


@admin.register(PortfolioComparison)
class PortfolioComparisonAdmin(admin.ModelAdmin):
    list_display = ("base_snapshot", "compare_snapshot", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "name",
        "slug",
        "base_snapshot__portfolio__name",
        "compare_snapshot__portfolio__name",
    )
    autocomplete_fields = ("base_snapshot", "compare_snapshot")
    list_select_related = ("base_snapshot", "compare_snapshot")
    actions = ("swap_snapshots",)

    @admin.action(description="Base/Compare snapshotlarını değiştir")
    def swap_snapshots(self, request, queryset):
        updated = 0
        for comparison in queryset:
            comparison.base_snapshot, comparison.compare_snapshot = (
                comparison.compare_snapshot,
                comparison.base_snapshot,
            )
            comparison.save(
                update_fields=["base_snapshot", "compare_snapshot", "updated_at"]
            )
            updated += 1
        self.message_user(
            request,
            f"{updated} karşılaştırma güncellendi.",
            level=messages.SUCCESS,
        )


class CashFlowEntryInline(admin.TabularInline):
    model = CashFlowEntry.cashflows.through
    extra = 0
    autocomplete_fields = ("cashflowentry",)


@admin.register(CashFlow)
class CashFlowAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("owner", "created_at")
    inlines = (CashFlowEntryInline,)
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
        if request.user.is_authenticated and request.user.is_staff:
            initial.setdefault("owner", request.user.pk)  # pyright: ignore[reportArgumentType]
        return initial

    @admin.action(description="Aylık nakit akışı snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        created = 0
        for cashflow in queryset:
            CashFlowSnapshot.create_snapshot(
                cashflow=cashflow,
                period=CashFlowSnapshot.Period.MONTHLY,
                snapshot_date=timezone.now().date(),  # pyright: ignore[reportArgumentType]
            )
            created += 1
        self.message_user(
            request,
            f"{created} adet snapshot oluşturuldu.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Yıllık nakit akışı snapshot oluştur")
    def create_yearly_snapshot(self, request, queryset):
        created = 0
        for cashflow in queryset:
            CashFlowSnapshot.create_snapshot(
                cashflow=cashflow,
                period=CashFlowSnapshot.Period.YEARLY,
                snapshot_date=timezone.now().date(),  # pyright: ignore[reportArgumentType]
            )
            created += 1
        self.message_user(
            request,
            f"{created} adet snapshot oluşturuldu.",
            level=messages.SUCCESS,
        )


@admin.register(CashFlowEntry)
class CashFlowEntryAdmin(admin.ModelAdmin):
    list_display = ("cashflows_display", "category", "entry_date", "amount", "currency")
    list_filter = ("category", "entry_date", "currency", "cashflows")
    search_fields = ("cashflows__name",)
    autocomplete_fields = ("cashflows",)

    @admin.display(description="Nakit Akışları")
    def cashflows_display(self, obj):
        return ", ".join(obj.cashflows.values_list("name", flat=True).order_by("name"))


class CashFlowSnapshotItemInline(admin.TabularInline):
    model = CashFlowSnapshotItem
    extra = 0
    readonly_fields = ("category", "amount", "allocation_pct")
    can_delete = False


@admin.register(CashFlowSnapshot)
class CashFlowSnapshotAdmin(admin.ModelAdmin):
    list_display = ("name", "cashflow", "period", "snapshot_date", "total_amount")
    list_filter = ("period", "snapshot_date")
    readonly_fields = ("total_amount",)
    search_fields = ("name", "slug", "cashflow__name", "cashflow__owner__email")
    list_select_related = ("cashflow", "cashflow__owner")
    inlines = (CashFlowSnapshotItemInline,)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        snapshot = CashFlowSnapshot.create_snapshot(
            cashflow=obj.cashflow,
            period=obj.period,
            snapshot_date=obj.snapshot_date,
            name=obj.name,
        )
        obj.pk = snapshot.pk
        obj.name = snapshot.name
        obj.total_amount = snapshot.total_amount


@admin.register(CashFlowComparison)
class CashFlowComparisonAdmin(admin.ModelAdmin):
    list_display = ("base_snapshot", "compare_snapshot", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "name",
        "slug",
        "base_snapshot__cashflow__name",
        "compare_snapshot__cashflow__name",
    )
    autocomplete_fields = ("base_snapshot", "compare_snapshot")
    list_select_related = ("base_snapshot", "compare_snapshot")
    actions = ("swap_snapshots",)

    @admin.action(description="Base/Compare snapshotlarını değiştir")
    def swap_snapshots(self, request, queryset):
        updated = 0
        for comparison in queryset:
            comparison.base_snapshot, comparison.compare_snapshot = (
                comparison.compare_snapshot,
                comparison.base_snapshot,
            )
            comparison.save(
                update_fields=["base_snapshot", "compare_snapshot", "updated_at"]
            )
            updated += 1
        self.message_user(
            request,
            f"{updated} karşılaştırma güncellendi.",
            level=messages.SUCCESS,
        )


@admin.register(DividendComparison)
class DividendComparisonAdmin(admin.ModelAdmin):
    list_display = ("base_snapshot", "compare_snapshot", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "slug", "base_snapshot__name", "compare_snapshot__name")
    autocomplete_fields = ("base_snapshot", "compare_snapshot")
    list_select_related = ("base_snapshot", "compare_snapshot")
    actions = ("swap_snapshots",)

    @admin.action(description="Base/Compare snapshotlarını değiştir")
    def swap_snapshots(self, request, queryset):
        updated = 0
        for comparison in queryset:
            comparison.base_snapshot, comparison.compare_snapshot = (
                comparison.compare_snapshot,
                comparison.base_snapshot,
            )
            comparison.save(
                update_fields=["base_snapshot", "compare_snapshot", "updated_at"]
            )
            updated += 1
        self.message_user(
            request,
            f"{updated} karşılaştırma güncellendi.",
            level=messages.SUCCESS,
        )


@admin.register(DividendPayment)
class DividendPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "payment_date",
        "share_count",
        "net_dividend_per_share",
        "average_cost",
        "last_close_price",
    )
    list_filter = ("payment_date", "asset")
    search_fields = ("asset__name", "asset__symbol")


@admin.register(Dividend)
class DividendAdmin(admin.ModelAdmin):
    list_display = ("payment", "currency", "per_share_net_amount", "total_net_amount")
    list_filter = ("currency", "payment__payment_date")
    search_fields = ("payment__asset__name", "payment__asset__symbol")
    autocomplete_fields = ("payment",)


class DividendSnapshotAssetInline(admin.TabularInline):
    model = DividendSnapshotAssetItem
    extra = 0
    readonly_fields = ("asset", "total_amount", "allocation_pct")
    can_delete = False


class DividendSnapshotPaymentInline(admin.TabularInline):
    model = DividendSnapshotPaymentItem
    extra = 0
    readonly_fields = (
        "asset",
        "payment",
        "payment_date",
        "per_share_net_amount",
        "dividend_yield_on_payment_price",
        "dividend_yield_on_average_cost",
        "total_net_amount",
    )
    can_delete = False


@admin.register(DividendSnapshot)
class DividendSnapshotAdmin(admin.ModelAdmin):
    list_display = ("name", "year", "currency", "total_amount")
    list_filter = ("year", "currency")
    readonly_fields = ("total_amount",)
    search_fields = ("name", "slug")
    inlines = (DividendSnapshotAssetInline, DividendSnapshotPaymentInline)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        snapshot = DividendSnapshot.create_snapshot(
            year=obj.year,
            currency=obj.currency,
            name=obj.name,
        )
        obj.pk = snapshot.pk
        obj.name = snapshot.name
        obj.total_amount = snapshot.total_amount
