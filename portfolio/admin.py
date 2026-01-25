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
    SalarySavingsEntry,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)

User = get_user_model()


def _get_staff_owner_queryset():
    return User.objects.filter(is_staff=True, socialaccount__isnull=True).distinct()


class StaffOwnerAdminMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = _get_staff_owner_queryset()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if request.user.is_authenticated and request.user.is_staff:
            initial.setdefault("owner", request.user.pk)  # pyright: ignore[reportArgumentType]
        return initial


class SnapshotCreatorAdminMixin:
    snapshot_model = None
    snapshot_relation_field = ""
    monthly_action_description = ""
    yearly_action_description = ""

    def _create_snapshots(self, queryset, *, period):
        created = 0
        for obj in queryset:
            self.snapshot_model.create_snapshot(
                **{
                    self.snapshot_relation_field: obj,
                    "period": period,
                    "snapshot_date": timezone.now().date(),  # pyright: ignore[reportArgumentType]
                }
            )
            created += 1
        return created

    def _notify_snapshots_created(self, request, count):
        self.message_user(
            request, f"{count} adet snapshot oluşturuldu.", level=messages.SUCCESS
        )

    @admin.action(description="Aylık snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        created = self._create_snapshots(
            queryset, period=self.snapshot_model.Period.MONTHLY
        )
        self._notify_snapshots_created(request, created)

    @admin.action(description="Yıllık snapshot oluştur")
    def create_yearly_snapshot(self, request, queryset):
        created = self._create_snapshots(
            queryset, period=self.snapshot_model.Period.YEARLY
        )
        self._notify_snapshots_created(request, created)


class SnapshotSwapAdminMixin:
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


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "asset_type", "currency", "current_price")
    search_fields = ("name", "symbol")
    list_filter = ("asset_type", "currency")
    readonly_fields = ("price_updated_at",)


@admin.register(Portfolio)
class PortfolioAdmin(StaffOwnerAdminMixin, SnapshotCreatorAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "target_value", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("owner", "created_at")
    inlines = ()

    actions = ("create_monthly_snapshot", "create_yearly_snapshot")
    snapshot_model = PortfolioSnapshot
    snapshot_relation_field = "portfolio"


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
class PortfolioComparisonAdmin(SnapshotSwapAdminMixin, admin.ModelAdmin):
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


class CashFlowEntryInline(admin.TabularInline):
    model = CashFlowEntry.cashflows.through
    extra = 0
    autocomplete_fields = ("cashflowentry",)


@admin.register(CashFlow)
class CashFlowAdmin(StaffOwnerAdminMixin, SnapshotCreatorAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("owner", "created_at")
    inlines = (CashFlowEntryInline,)
    actions = ("create_monthly_snapshot", "create_yearly_snapshot")
    snapshot_model = CashFlowSnapshot
    snapshot_relation_field = "cashflow"

    @admin.action(description="Aylık nakit akışı snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        super().create_monthly_snapshot(request, queryset)

    @admin.action(description="Yıllık nakit akışı snapshot oluştur")
    def create_yearly_snapshot(self, request, queryset):
        super().create_yearly_snapshot(request, queryset)


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
class CashFlowComparisonAdmin(SnapshotSwapAdminMixin, admin.ModelAdmin):
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


@admin.register(SalarySavingsFlow)
class SalarySavingsFlowAdmin(StaffOwnerAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "created_at")
    search_fields = ("name", "owner__email")
    list_filter = ("owner", "created_at")
    actions = ("create_monthly_snapshot",)

    @admin.action(description="Aylık maaş/tasarruf snapshot oluştur")
    def create_monthly_snapshot(self, request, queryset):
        created = 0
        for flow in queryset:
            SalarySavingsSnapshot.create_snapshot(
                flow=flow,
                snapshot_date=timezone.now().date(),  # pyright: ignore[reportArgumentType]
            )
            created += 1
        self.message_user(
            request,
            f"{created} adet snapshot oluşturuldu.",
            level=messages.SUCCESS,
        )


@admin.register(SalarySavingsEntry)
class SalarySavingsEntryAdmin(admin.ModelAdmin):
    list_display = (
        "flow",
        "entry_date",
        "salary_amount",
        "savings_amount",
        "savings_rate_display",
    )
    list_filter = ("flow", "entry_date")
    search_fields = ("flow__name", "flow__owner__email")
    list_select_related = ("flow", "flow__owner")
    autocomplete_fields = ("flow",)

    @admin.display(description="Tasarruf Oranı (%)")
    def savings_rate_display(self, obj):
        if not obj.salary_amount:
            return "0.00"
        return f"{float((obj.savings_amount / obj.salary_amount) * 100):.2f}"


@admin.register(SalarySavingsSnapshot)
class SalarySavingsSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "flow",
        "snapshot_date",
        "savings_rate_display",
        "total_salary",
        "total_savings",
    )
    list_filter = ("snapshot_date",)
    readonly_fields = ("total_salary", "total_savings", "savings_rate")
    search_fields = ("name", "slug", "flow__name", "flow__owner__email")
    list_select_related = ("flow", "flow__owner")
    autocomplete_fields = ("flow",)

    @admin.display(description="Tasarruf Oranı (%)")
    def savings_rate_display(self, obj):
        return f"{float((obj.savings_rate or 0) * 100):.2f}"

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        snapshot = SalarySavingsSnapshot.create_snapshot(
            flow=obj.flow,
            snapshot_date=obj.snapshot_date,
            name=obj.name,
        )
        obj.pk = snapshot.pk
        obj.name = snapshot.name
        obj.total_salary = snapshot.total_salary
        obj.total_savings = snapshot.total_savings
        obj.savings_rate = snapshot.savings_rate


@admin.register(DividendComparison)
class DividendComparisonAdmin(SnapshotSwapAdminMixin, admin.ModelAdmin):
    list_display = ("base_snapshot", "compare_snapshot", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "slug", "base_snapshot__name", "compare_snapshot__name")
    autocomplete_fields = ("base_snapshot", "compare_snapshot")
    list_select_related = ("base_snapshot", "compare_snapshot")
    actions = ("swap_snapshots",)


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
    list_display = ("name", "year", "snapshot_date", "currency", "total_amount")
    list_filter = ("year", "snapshot_date", "currency")
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
            snapshot_date=obj.snapshot_date,
            name=obj.name,
        )
        obj.pk = snapshot.pk
        obj.name = snapshot.name
        obj.total_amount = snapshot.total_amount
