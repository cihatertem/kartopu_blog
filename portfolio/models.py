from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.mixins import TimeStampedModelMixin, UUIDModelMixin
from core.services.portfolio import (
    build_comparison_name,
    build_snapshot_name,
    format_comparison_label,
    format_snapshot_label,
    generate_unique_slug,
)
from portfolio.services import calculate_xirr, fetch_fx_rate, fetch_yahoo_finance_price

MAX_DICITS = 200
MAX_DECIMAL_PLACES = 4
MAX_DECIMAL_PLACES_FOR_QUANTITY = 5


class Asset(UUIDModelMixin, TimeStampedModelMixin):
    class AssetType(models.TextChoices):
        STOCK = "stock", "Hisse"
        BIST = "bist", "BIST"
        SPX = "abd stock", "ABD Hisse"
        BES = "bes", "BES"
        ETF = "etf", "ETF"
        FON = "fon", "Yatırım Fonu"
        BOND = "bond", "Tahvil"
        EUROBOND = "eurobond", "Eurobond"
        VIOP = "viop", "VİOP"
        CASH = "cash", "Nakit"
        CRYPTO = "crypto", "Kripto"
        GOLD = "gold", "Altın"
        OTHER = "other", "Diğer"

    class Currency(models.TextChoices):
        TRY = "TRY", "TRY"
        USD = "USD", "USD"
        EUR = "EUR", "EUR"

    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=30, blank=True)
    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    currency = models.CharField(
        max_length=10, default=Currency.TRY, choices=Currency.choices
    )
    current_price = models.DecimalField(
        max_digits=MAX_DICITS,
        decimal_places=MAX_DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    price_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Varlık"
        verbose_name_plural = "Varlıklar"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})" if self.symbol else self.name

    def refresh_price(self, price_date: date | None = None) -> Decimal | None:
        if not self.symbol:
            return None

        price = fetch_yahoo_finance_price(self.symbol, price_date=price_date)
        if price is None:
            return None

        if price_date is None:
            self.current_price = price
            self.price_updated_at = timezone.now()

        return price

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding and self.symbol and not self.current_price:
            self.refresh_price()

        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class PortfolioComparison(UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    base_snapshot = models.ForeignKey(
        "PortfolioSnapshot",
        on_delete=models.CASCADE,
        related_name="base_comparisons",
    )
    compare_snapshot = models.ForeignKey(
        "PortfolioSnapshot",
        on_delete=models.CASCADE,
        related_name="compare_comparisons",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy Karşılaştırması"
        verbose_name_plural = "Portföy Karşılaştırmaları"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return format_comparison_label(
            slug=self.slug,
            name=self.name,
            base_snapshot=self.base_snapshot,
            compare_snapshot=self.compare_snapshot,
        )

    def clean(self) -> None:
        if (
            self.base_snapshot
            and self.compare_snapshot
            and self.base_snapshot.portfolio_id != self.compare_snapshot.portfolio_id
        ):
            raise ValidationError(
                "Karşılaştırma snapshotları aynı portföye ait olmalıdır."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name:
            self.name = build_comparison_name(self.base_snapshot, self.compare_snapshot)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class Portfolio(UUIDModelMixin, TimeStampedModelMixin):
    class Currency(models.TextChoices):
        TRY = "TRY", "TRY"
        USD = "USD", "USD"
        EUR = "EUR", "EUR"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=200)
    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.TRY,
    )
    target_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy"
        verbose_name_plural = "Portföyler"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name}"

    def get_positions(
        self,
        *,
        price_date: date | None = None,
    ) -> list[dict[str, Decimal | Asset]]:
        positions: dict[str, dict[str, Decimal | Asset]] = {}
        transactions = (
            self.transactions.select_related(  # pyright: ignore[reportAttributeAccessIssue]
                "asset"
            )
            .order_by("trade_date", "created_at")
            .distinct()
        )
        if price_date:
            transactions = transactions.filter(trade_date__lte=price_date)
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}

        for transaction in transactions:
            asset = transaction.asset
            # Use price_date (snapshot date) for conversion if provided, otherwise historical
            conversion_date = price_date or transaction.trade_date
            currency_pair = (asset.currency, self.currency, conversion_date)
            if currency_pair not in fx_rates:
                fx_rate = fetch_fx_rate(
                    asset.currency,
                    self.currency,
                    rate_date=conversion_date,
                )
                fx_rates[currency_pair] = (
                    fx_rate if fx_rate is not None else Decimal("1")
                )
            fx_rate = fx_rates[currency_pair]
            data = positions.setdefault(
                str(asset.id),
                {
                    "asset": asset,
                    "quantity": Decimal("0"),
                    "cost_basis": Decimal("0"),
                },
            )
            quantity = data["quantity"]
            cost_basis = data["cost_basis"]
            transaction_cost = transaction.total_cost * fx_rate

            if transaction.transaction_type == PortfolioTransaction.TransactionType.BUY:
                quantity += transaction.quantity
                cost_basis += transaction_cost
            elif (
                transaction.transaction_type
                == PortfolioTransaction.TransactionType.SELL
            ):
                if quantity > 0:  # pyright: ignore[reportOperatorIssue]
                    average_cost = cost_basis / quantity  # pyright: ignore[reportOperatorIssue]
                    cost_basis -= average_cost * transaction.quantity
                quantity -= transaction.quantity

            if quantity <= 0:  # pyright: ignore [reportOperatorIssue]
                quantity = Decimal("0")
                cost_basis = Decimal("0")

            data["quantity"] = quantity
            data["cost_basis"] = cost_basis

        total_value = Decimal("0")
        for data in positions.values():
            asset = data["asset"]
            quantity = data["quantity"]
            current_price = asset.current_price or Decimal("0")  # pyright: ignore[reportAttributeAccessIssue]
            if price_date and asset.symbol:  # pyright: ignore[reportAttributeAccessIssue]
                fetched_price = fetch_yahoo_finance_price(
                    asset.symbol,  # pyright: ignore[reportAttributeAccessIssue]
                    price_date=price_date,
                )
                if fetched_price is not None:
                    current_price = fetched_price
            elif not current_price and asset.symbol:  # pyright: ignore[reportAttributeAccessIssue]
                fetched_price = fetch_yahoo_finance_price(asset.symbol)  # pyright: ignore[reportAttributeAccessIssue]
                if fetched_price is not None:
                    current_price = fetched_price
            currency_pair = (asset.currency, self.currency, price_date)  # pyright: ignore[reportAttributeAccessIssue]
            fx_rate = fx_rates.get(currency_pair)

            if fx_rate is None:
                fx_rate = fetch_fx_rate(
                    asset.currency,  # pyright: ignore[reportAttributeAccessIssue]
                    self.currency,
                    rate_date=price_date,
                )  # pyright: ignore[reportAttributeAccessIssue]
                fx_rate = fx_rate if fx_rate is not None else Decimal("1")
                fx_rates[currency_pair] = fx_rate

            converted_price = current_price * fx_rate
            data["current_price"] = converted_price
            data["market_value"] = quantity * converted_price  # pyright: ignore[reportOperatorIssue]
            total_value += data["market_value"]

        for data in positions.values():
            cost_basis = data["cost_basis"]
            market_value = data["market_value"]
            data["average_cost"] = (
                cost_basis / data["quantity"] if data["quantity"] > 0 else Decimal("0")  # pyright: ignore[reportOperatorIssue]
            )
            data["gain_loss"] = market_value - cost_basis  # pyright: ignore[reportOperatorIssue]
            data["gain_loss_pct"] = (
                (market_value - cost_basis) / cost_basis  # pyright: ignore[reportOperatorIssue]
                if cost_basis > 0  # pyright: ignore[reportOperatorIssue]
                else Decimal("0")
            )
            data["allocation_pct"] = (
                market_value / total_value if total_value > 0 else Decimal("0")  # pyright: ignore[reportOperatorIssue]
            )

        return list(positions.values())

    def total_market_value(self) -> Decimal:
        return sum(  # pyright: ignore[reportCallIssue]
            (position["market_value"] for position in self.get_positions()),  # pyright: ignore[reportArgumentType]
            Decimal("0"),
        )

    def total_cost_basis(self) -> Decimal:
        return sum(  # pyright: ignore[reportCallIssue]
            (position["cost_basis"] for position in self.get_positions()),  # pyright: ignore[reportArgumentType]
            Decimal("0"),
        )

    def get_irr_history(self, until_date: date | None = None) -> list[dict]:
        """
        Returns the IRR performance history based on snapshots.
        If until_date is provided, only snapshots up to that date are included.
        """
        snapshots = self.snapshots.filter(irr_pct__isnull=False).order_by(  # pyright: ignore[reportAttributeAccessIssue]
            "snapshot_date"
        )
        if until_date:
            snapshots = snapshots.filter(snapshot_date__lte=until_date)

        if not snapshots:
            return []

        return [
            {
                "date": snapshot.snapshot_date.isoformat(),
                "irr": float(snapshot.irr_pct),
            }
            for snapshot in snapshots
        ]


class PortfolioTransaction(UUIDModelMixin, TimeStampedModelMixin):
    class TransactionType(models.TextChoices):
        BUY = "buy", "Alım"
        SELL = "sell", "Satış"
        DIVIDEND = "dividend", "Temettü"
        COUPON = "coupon", "Kupon Ödemesi"

    portfolios = models.ManyToManyField(
        Portfolio,
        related_name="transactions",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        default=TransactionType.BUY,
    )
    trade_date = models.DateField()
    quantity = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    price_per_unit = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy İşlemi"
        verbose_name_plural = "Portföy İşlemleri"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.asset.current_price or not self.asset.price_updated_at:
            self.asset.refresh_price()
            self.asset.save(
                update_fields=["current_price", "price_updated_at", "updated_at"]
            )

        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    def __str__(self) -> str:
        portfolio_names = list(
            self.portfolios.values_list("name", flat=True).order_by("name")
        )
        if portfolio_names:
            return f"{', '.join(portfolio_names)} - {self.asset}"
        return f"{self.asset}"

    @property
    def total_cost(self) -> Decimal:
        return self.quantity * self.price_per_unit


class PortfolioSnapshot(UUIDModelMixin, TimeStampedModelMixin):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Aylık"
        YEARLY = "yearly", "Yıllık"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    period = models.CharField(max_length=10, choices=Period.choices)
    snapshot_date = models.DateField(default=timezone.now)
    name = models.CharField(max_length=200, blank=True)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    total_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_cost = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    target_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_return_pct = models.DecimalField(
        max_digits=10, decimal_places=MAX_DECIMAL_PLACES
    )
    irr_pct = models.DecimalField(
        max_digits=10, decimal_places=MAX_DECIMAL_PLACES, null=True, blank=True
    )
    is_featured = models.BooleanField(default=False)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy Snapshot"
        verbose_name_plural = "Portföy Snapshotları"
        ordering = ("-snapshot_date", "-created_at")

    def __str__(self) -> str:
        return format_snapshot_label(
            slug=self.slug,
            name=self.name,
            owner_label=f"{self.portfolio}",
            snapshot_date=self.snapshot_date,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name and self.portfolio_id and self.snapshot_date:  # pyright: ignore[reportAttributeAccessIssue]
            self.name = build_snapshot_name(f"{self.portfolio}", self.snapshot_date)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def create_snapshot(
        cls,
        *,
        portfolio: Portfolio,
        period: str,
        snapshot_date: timezone.datetime | None = None,
        name: str | None = None,
    ) -> "PortfolioSnapshot":
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]

        positions = portfolio.get_positions(price_date=snapshot_date)
        total_value = sum(  # pyright: ignore[reportCallIssue]
            (position["market_value"] for position in positions),  # pyright: ignore[reportArgumentType]
            Decimal("0"),
        )
        total_cost = sum(  # pyright: ignore[reportCallIssue]
            (position["cost_basis"] for position in positions),  # pyright: ignore[reportArgumentType]
            Decimal("0"),
        )
        total_return_pct = (
            (total_value - total_cost) / total_cost if total_cost > 0 else Decimal("0")
        )

        # Calculate IRR
        transactions = portfolio.transactions.select_related("asset").filter(  # pyright: ignore[reportAttributeAccessIssue]
            trade_date__lte=snapshot_date
        )
        tx_cash_flows = []
        for tx in transactions:
            fx_rate = fetch_fx_rate(
                tx.asset.currency, portfolio.currency, rate_date=tx.trade_date
            )
            fx_rate = fx_rate if fx_rate is not None else Decimal("1")
            amount = tx.total_cost * fx_rate
            if tx.transaction_type == PortfolioTransaction.TransactionType.BUY:
                tx_cash_flows.append((tx.trade_date, -amount))
            else:
                tx_cash_flows.append((tx.trade_date, amount))

        tx_cash_flows.append((snapshot_date, total_value))
        irr = calculate_xirr(tx_cash_flows)
        irr_pct = Decimal(str(irr)) * 100 if irr is not None else None

        snapshot = cls.objects.create(
            portfolio=portfolio,
            period=period,
            snapshot_date=snapshot_date,
            name=name or "",
            total_value=total_value,
            total_cost=total_cost,
            target_value=portfolio.target_value,
            total_return_pct=total_return_pct,
            irr_pct=irr_pct,
        )

        for position in positions:
            PortfolioSnapshotItem.objects.create(
                snapshot=snapshot,
                asset=position["asset"],
                quantity=position["quantity"],
                average_cost=position["average_cost"],
                cost_basis=position["cost_basis"],
                current_price=position["current_price"],
                market_value=position["market_value"],
                allocation_pct=position["allocation_pct"],
                gain_loss=position["gain_loss"],
                gain_loss_pct=position["gain_loss_pct"],
            )

        return snapshot


class PortfolioSnapshotItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        PortfolioSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    quantity = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    average_cost = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    cost_basis = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    current_price = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    market_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(max_digits=10, decimal_places=4)
    gain_loss = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    gain_loss_pct = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Snapshot Kalemi"
        verbose_name_plural = "Snapshot Kalemleri"

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.asset}"


class CashFlow(UUIDModelMixin, TimeStampedModelMixin):
    class Currency(models.TextChoices):
        TRY = "TRY", "TRY"
        USD = "USD", "USD"
        EUR = "EUR", "EUR"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cashflows",
    )
    name = models.CharField(max_length=200)
    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.TRY,
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı"
        verbose_name_plural = "Nakit Akışları"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name


class CashFlowEntry(UUIDModelMixin, TimeStampedModelMixin):
    class Category(models.TextChoices):
        DIVIDEND = "dividend", "Temettü"
        INTEREST = "interest", "Faiz/Nema"
        EUROBOND_COUPON = "eurobond_coupon", "Eurobond Kupon"
        CREDIT_CARD_BONUS = "credit_card_bonus", "Kredi Kartı Bonus"
        OTHER = "other", "Diğer"

    cashflows = models.ManyToManyField(
        CashFlow,
        related_name="entries",
    )
    entry_date = models.DateField()
    category = models.CharField(max_length=30, choices=Category.choices)
    amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    currency = models.CharField(
        max_length=10,
        choices=CashFlow.Currency.choices,
        default=CashFlow.Currency.TRY,
    )
    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı Girişi"
        verbose_name_plural = "Nakit Akışı Girişleri"
        ordering = ("-created_at", "-entry_date")

    def __str__(self) -> str:
        cashflows = ", ".join(
            self.cashflows.values_list("name", flat=True).order_by("name")
        )
        return f"{cashflows or 'Nakit Akışı Yok'} - {self.get_category_display()}"  # pyright: ignore[reportAttributeAccessIssue]


class CashFlowSnapshot(UUIDModelMixin, TimeStampedModelMixin):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Aylık"
        YEARLY = "yearly", "Yıllık"

    cashflow = models.ForeignKey(
        CashFlow,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    period = models.CharField(max_length=10, choices=Period.choices)
    snapshot_date = models.DateField(default=timezone.now)
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="İsimlendirme yapılmazsa CashFlow adı kullanılır.",
    )
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    total_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı Snapshot"
        verbose_name_plural = "Nakit Akışı Snapshotları"
        ordering = ("-snapshot_date", "-created_at")

    def __str__(self) -> str:
        return format_snapshot_label(
            slug=self.slug,
            name=self.name,
            owner_label=f"{self.cashflow}",
            snapshot_date=self.snapshot_date,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name and self.cashflow_id:  # pyright: ignore[reportAttributeAccessIssue]
            self.name = build_snapshot_name(f"{self.cashflow}", self.snapshot_date)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def create_snapshot(
        cls,
        *,
        cashflow: CashFlow,
        period: str,
        snapshot_date: date | None = None,
        name: str | None = None,
    ) -> "CashFlowSnapshot":
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]

        if period == cls.Period.MONTHLY:
            start_date = snapshot_date.replace(day=1)
            last_day = calendar.monthrange(snapshot_date.year, snapshot_date.month)[1]
            end_date = snapshot_date.replace(day=last_day)
        else:
            start_date = snapshot_date.replace(month=1, day=1)
            end_date = snapshot_date.replace(month=12, day=31)
        if snapshot_date < end_date:
            end_date = snapshot_date

        entries = CashFlowEntry.objects.filter(
            cashflows=cashflow,
            entry_date__gte=start_date,
            entry_date__lte=end_date,
        ).values("category", "amount", "currency", "entry_date")

        category_totals: dict[str, Decimal] = {}
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}

        for entry in entries:
            amount = entry["amount"] or Decimal("0")
            entry_currency = entry["currency"]
            fx_rate = Decimal("1")
            if entry_currency != cashflow.currency:
                # Use snapshot_date for currency conversion
                currency_pair = (entry_currency, cashflow.currency, snapshot_date)
                fx_rate = fx_rates.get(currency_pair)
                if fx_rate is None:
                    fetched_rate = fetch_fx_rate(
                        entry_currency,
                        cashflow.currency,
                        rate_date=snapshot_date,
                    )
                    fx_rate = fetched_rate if fetched_rate is not None else Decimal("1")
                    fx_rates[currency_pair] = fx_rate
            converted_amount = amount * fx_rate
            category_totals[entry["category"]] = (
                category_totals.get(entry["category"], Decimal("0")) + converted_amount
            )

        total_amount = sum(  # pyright: ignore[reportCallIssue]
            category_totals.values(),  # pyright: ignore[reportArgumentType]
            Decimal("0"),
        )

        snapshot = cls.objects.create(
            cashflow=cashflow,
            period=period,
            snapshot_date=snapshot_date,
            name=name or cashflow.name,
            total_amount=total_amount,
        )

        for category, amount in sorted(category_totals.items()):
            allocation_pct = amount / total_amount if total_amount > 0 else Decimal("0")
            CashFlowSnapshotItem.objects.create(
                snapshot=snapshot,
                category=category,
                amount=amount,
                allocation_pct=allocation_pct,
            )

        return snapshot


class CashFlowSnapshotItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        CashFlowSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.CharField(max_length=30, choices=CashFlowEntry.Category.choices)
    amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı Snapshot Kalemi"
        verbose_name_plural = "Nakit Akışı Snapshot Kalemleri"

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.get_category_display()}"  # pyright: ignore[reportAttributeAccessIssue]


class CashFlowComparison(UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    base_snapshot = models.ForeignKey(
        CashFlowSnapshot,
        on_delete=models.CASCADE,
        related_name="base_comparisons",
    )
    compare_snapshot = models.ForeignKey(
        CashFlowSnapshot,
        on_delete=models.CASCADE,
        related_name="compare_comparisons",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı Karşılaştırması"
        verbose_name_plural = "Nakit Akışı Karşılaştırmaları"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return format_comparison_label(
            slug=self.slug,
            name=self.name,
            base_snapshot=self.base_snapshot,
            compare_snapshot=self.compare_snapshot,
        )

    def clean(self) -> None:
        if (
            self.base_snapshot
            and self.compare_snapshot
            and self.base_snapshot.cashflow_id != self.compare_snapshot.cashflow_id  # pyright: ignore[reportAttributeAccessIssue]
        ):
            raise ValidationError(
                "Karşılaştırma snapshotları aynı nakit akışına ait olmalıdır."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name:
            self.name = build_comparison_name(self.base_snapshot, self.compare_snapshot)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class SalarySavingsFlow(UUIDModelMixin, TimeStampedModelMixin):
    class Currency(models.TextChoices):
        TRY = "TRY", "TRY"
        USD = "USD", "USD"
        EUR = "EUR", "EUR"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_savings_flows",
    )
    name = models.CharField(max_length=200)
    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.TRY,
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Maaş/Tasarruf Akışı"
        verbose_name_plural = "Maaş/Tasarruf Akışları"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name


class SalarySavingsEntry(UUIDModelMixin, TimeStampedModelMixin):
    flow = models.ForeignKey(
        SalarySavingsFlow,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    entry_date = models.DateField()
    salary_amount = models.DecimalField(
        max_digits=MAX_DICITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    savings_amount = models.DecimalField(
        max_digits=MAX_DICITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Maaş/Tasarruf Girişi"
        verbose_name_plural = "Maaş/Tasarruf Girişleri"
        ordering = ("-entry_date", "-created_at")

    def __str__(self) -> str:
        return f"{self.flow} - {self.entry_date}"


class SalarySavingsSnapshot(UUIDModelMixin, TimeStampedModelMixin):
    flow = models.ForeignKey(
        SalarySavingsFlow,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    snapshot_date = models.DateField(default=timezone.now)
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="İsimlendirme yapılmazsa akış adı ve tarih kullanılır.",
    )
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    total_salary = models.DecimalField(
        max_digits=MAX_DICITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    total_savings = models.DecimalField(
        max_digits=MAX_DICITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    savings_rate = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Maaş/Tasarruf Snapshot"
        verbose_name_plural = "Maaş/Tasarruf Snapshotları"
        ordering = ("-snapshot_date", "-created_at")

    def __str__(self) -> str:
        return format_snapshot_label(
            slug=self.slug,
            name=self.name,
            owner_label=f"{self.flow}",
            snapshot_date=self.snapshot_date,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name and self.flow_id:  # pyright: ignore[reportAttributeAccessIssue]
            self.name = build_snapshot_name(f"{self.flow}", self.snapshot_date)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def create_snapshot(
        cls,
        *,
        flow: SalarySavingsFlow,
        snapshot_date: date | None = None,
        name: str | None = None,
    ) -> "SalarySavingsSnapshot":
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]
        start_date = snapshot_date.replace(day=1)
        last_day = calendar.monthrange(snapshot_date.year, snapshot_date.month)[1]
        end_date = snapshot_date.replace(day=last_day)
        if snapshot_date < end_date:
            end_date = snapshot_date

        totals = list(
            flow.entries.filter(  # pyright: ignore[reportAttributeAccessIssue]
                entry_date__gte=start_date,
                entry_date__lte=end_date,
            ).values_list("salary_amount", "savings_amount")
        )

        total_salary = sum(
            ((salary or Decimal("0")) for salary, _ in totals),
            Decimal("0"),
        )
        total_savings = sum(
            ((savings or Decimal("0")) for _, savings in totals),
            Decimal("0"),
        )
        savings_rate = (
            total_savings / total_salary if total_salary > 0 else Decimal("0")
        )

        snapshot = cls.objects.create(
            flow=flow,
            snapshot_date=snapshot_date,
            name=name or "",
            total_salary=total_salary,
            total_savings=total_savings,
            savings_rate=savings_rate,
        )
        return snapshot


class DividendComparison(UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    base_snapshot = models.ForeignKey(
        "DividendSnapshot",
        on_delete=models.CASCADE,
        related_name="base_comparisons",
    )
    compare_snapshot = models.ForeignKey(
        "DividendSnapshot",
        on_delete=models.CASCADE,
        related_name="compare_comparisons",
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Karşılaştırması"
        verbose_name_plural = "Temettü Karşılaştırmaları"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return format_comparison_label(
            slug=self.slug,
            name=self.name,
            base_snapshot=self.base_snapshot,
            compare_snapshot=self.compare_snapshot,
        )

    def clean(self) -> None:
        if (
            self.base_snapshot
            and self.compare_snapshot
            and self.base_snapshot.currency != self.compare_snapshot.currency
        ):
            raise ValidationError(
                "Karşılaştırma snapshotlarının para birimleri aynı olmalıdır."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name:
            self.name = build_comparison_name(self.base_snapshot, self.compare_snapshot)
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class DividendPayment(UUIDModelMixin, TimeStampedModelMixin):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="dividend_payments",
    )
    payment_date = models.DateField()
    share_count = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    net_dividend_per_share = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    average_cost = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    last_close_price = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Ödemesi"
        verbose_name_plural = "Temettü Ödemeleri"
        ordering = ("-payment_date", "-created_at")

    def __str__(self) -> str:
        return f"{self.asset} - {self.payment_date}"

    @property
    def total_net_amount(self) -> Decimal:
        return self.share_count * self.net_dividend_per_share

    @property
    def dividend_yield_on_payment_price(self) -> Decimal:
        if self.last_close_price:
            return self.net_dividend_per_share / self.last_close_price
        return Decimal("0")

    @property
    def dividend_yield_on_average_cost(self) -> Decimal:
        if self.average_cost:
            return self.net_dividend_per_share / self.average_cost
        return Decimal("0")

    def sync_dividend_currencies(self) -> None:
        base_currency = self.asset.currency
        total_amount = self.total_net_amount
        for currency, _ in Asset.Currency.choices:
            fx_rate = Decimal("1")
            if base_currency != currency:
                fetched_rate = fetch_fx_rate(
                    base_currency,
                    currency,
                    rate_date=self.payment_date,
                )
                fx_rate = fetched_rate if fetched_rate is not None else Decimal("1")
            per_share = self.net_dividend_per_share * fx_rate
            total_converted = total_amount * fx_rate
            Dividend.objects.update_or_create(
                payment=self,
                currency=currency,
                defaults={
                    "per_share_net_amount": per_share,
                    "total_net_amount": total_converted,
                },
            )

    def save(self, *args: object, **kwargs: object) -> None:
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        self.sync_dividend_currencies()


class Dividend(UUIDModelMixin, TimeStampedModelMixin):
    payment = models.ForeignKey(
        DividendPayment,
        on_delete=models.CASCADE,
        related_name="dividends",
    )
    currency = models.CharField(
        max_length=10,
        choices=Asset.Currency.choices,
        default=Asset.Currency.TRY,
    )
    per_share_net_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_net_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü"
        verbose_name_plural = "Temettüler"
        constraints = [
            models.UniqueConstraint(
                fields=("payment", "currency"),
                name="unique_dividend_payment_currency",
            )
        ]

    def __str__(self) -> str:
        return f"{self.payment} ({self.currency})"


class DividendSnapshot(UUIDModelMixin, TimeStampedModelMixin):
    year = models.PositiveIntegerField()
    currency = models.CharField(
        max_length=10,
        choices=Asset.Currency.choices,
        default=Asset.Currency.TRY,
    )
    snapshot_date = models.DateField(default=timezone.now)
    name = models.CharField(max_length=200, blank=True)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    total_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Snapshot"
        verbose_name_plural = "Temettü Snapshotları"
        ordering = ("-snapshot_date", "-created_at")

    def __str__(self) -> str:
        if self.slug:
            return self.slug
        return self.name or f"{self.year} Temettü"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name and self.year:
            self.name = f"{self.year} Temettü Özeti"
        if not self.slug and self.name:
            self.slug = generate_unique_slug(self.__class__, self.name)
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def create_snapshot(
        cls,
        *,
        year: int,
        currency: str,
        snapshot_date: date | None = None,
        name: str | None = None,
    ) -> "DividendSnapshot":
        snapshot_date = snapshot_date or date(year, 12, 31)
        payments = (
            DividendPayment.objects.select_related("asset")
            .filter(payment_date__year=year, payment_date__lte=snapshot_date)
            .order_by("payment_date", "created_at")
        )

        total_amount = Decimal("0")
        asset_totals: dict[str, dict[str, Decimal | Asset]] = {}
        payment_rows: list[dict[str, object]] = []

        for payment in payments:
            fx_rate = Decimal("1")
            if payment.asset.currency != currency:
                # Use snapshot_date for currency conversion
                fetched_rate = fetch_fx_rate(
                    payment.asset.currency,
                    currency,
                    rate_date=snapshot_date,
                )
                fx_rate = fetched_rate if fetched_rate is not None else Decimal("1")
            per_share = payment.net_dividend_per_share * fx_rate
            total_payment = payment.total_net_amount * fx_rate
            avg_cost = payment.average_cost * fx_rate
            last_close = payment.last_close_price * fx_rate
            yield_on_payment = (
                per_share / last_close if last_close > 0 else Decimal("0")
            )
            yield_on_average = per_share / avg_cost if avg_cost > 0 else Decimal("0")
            total_amount += total_payment
            asset_entry = asset_totals.setdefault(
                str(payment.asset_id),  # pyright: ignore[reportAttributeAccessIssue]
                {"asset": payment.asset, "total_amount": Decimal("0")},
            )
            asset_entry["total_amount"] = (
                asset_entry["total_amount"] + total_payment  # pyright: ignore[reportOperatorIssue]
            )
            payment_rows.append(
                {
                    "asset": payment.asset,
                    "payment": payment,
                    "payment_date": payment.payment_date,
                    "per_share_net_amount": per_share,
                    "dividend_yield_on_payment_price": yield_on_payment,
                    "dividend_yield_on_average_cost": yield_on_average,
                    "total_net_amount": total_payment,
                }
            )

        snapshot = cls.objects.create(
            year=year,
            currency=currency,
            snapshot_date=snapshot_date,
            name=name or f"{year} Temettü Özeti",
            total_amount=total_amount,
        )

        for asset_entry in asset_totals.values():
            amount = asset_entry["total_amount"]
            allocation_pct = amount / total_amount if total_amount > 0 else Decimal("0")  # pyright: ignore[reportOperatorIssue]
            DividendSnapshotAssetItem.objects.create(
                snapshot=snapshot,
                asset=asset_entry["asset"],
                total_amount=amount,
                allocation_pct=allocation_pct,
            )

        for row in payment_rows:
            DividendSnapshotPaymentItem.objects.create(
                snapshot=snapshot,
                asset=row["asset"],
                payment=row["payment"],
                payment_date=row["payment_date"],
                per_share_net_amount=row["per_share_net_amount"],
                dividend_yield_on_payment_price=row["dividend_yield_on_payment_price"],
                dividend_yield_on_average_cost=row["dividend_yield_on_average_cost"],
                total_net_amount=row["total_net_amount"],
            )

        return snapshot


class DividendSnapshotAssetItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        DividendSnapshot,
        on_delete=models.CASCADE,
        related_name="asset_items",
    )
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    total_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Snapshot Varlığı"
        verbose_name_plural = "Temettü Snapshot Varlıkları"

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.asset}"


class DividendSnapshotPaymentItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        DividendSnapshot,
        on_delete=models.CASCADE,
        related_name="payment_items",
    )
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    payment = models.ForeignKey(DividendPayment, on_delete=models.CASCADE)
    payment_date = models.DateField()
    per_share_net_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    dividend_yield_on_payment_price = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    dividend_yield_on_average_cost = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_net_amount = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Snapshot Ödeme Kalemi"
        verbose_name_plural = "Temettü Snapshot Ödeme Kalemleri"
        ordering = ("payment_date", "created_at")

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.asset} - {self.payment_date}"
