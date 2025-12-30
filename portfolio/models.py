from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.mixins import TimeStampedModelMixin, UUIDModelMixin
from portfolio.services import fetch_fx_rate, fetch_yahoo_finance_price

MAX_DICITS = 200
MAX_DECIMAL_PLACES = 2


class Asset(UUIDModelMixin, TimeStampedModelMixin):
    class AssetType(models.TextChoices):
        STOCK = "stock", "Hisse"
        ETF = "etf", "ETF"
        CRYPTO = "crypto", "Kripto"
        EUROBOND = "eurobond", "Eurobond"
        CASH = "cash", "Nakit"
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

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})" if self.symbol else self.name

    def refresh_price(self) -> None:
        if not self.symbol:
            return

        price = fetch_yahoo_finance_price(self.symbol)
        if price is None:
            return

        self.current_price = price
        self.price_updated_at = timezone.now()

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding and self.symbol and not self.current_price:
            self.refresh_price()

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

    def __str__(self) -> str:
        return f"{self.name}"

    def get_positions(self) -> list[dict[str, Decimal | Asset]]:
        positions: dict[str, dict[str, Decimal | Asset]] = {}
        transactions = (
            self.transactions.select_related("asset")  # pyright: ignore[reportAttributeAccessIssue]
            .all()
            .order_by("trade_date", "created_at")
        )
        fx_rates: dict[tuple[str, str], Decimal] = {}

        for transaction in transactions:
            asset = transaction.asset
            currency_pair = (asset.currency, self.currency)
            if currency_pair not in fx_rates:
                fx_rate = fetch_fx_rate(asset.currency, self.currency)
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
            else:
                if quantity > 0:  # pyright: ignore[reportOperatorIssue]
                    average_cost = cost_basis / quantity  # pyright: ignore[reportOperatorIssue]
                    cost_basis -= average_cost * transaction.quantity
                quantity -= transaction.quantity

            if quantity <= 0:
                quantity = Decimal("0")
                cost_basis = Decimal("0")

            data["quantity"] = quantity
            data["cost_basis"] = cost_basis

        total_value = Decimal("0")
        for data in positions.values():
            asset = data["asset"]
            quantity = data["quantity"]
            current_price = asset.current_price or Decimal("0")  # pyright: ignore[reportAttributeAccessIssue]
            currency_pair = (asset.currency, self.currency)  # pyright: ignore[reportAttributeAccessIssue]
            fx_rate = fx_rates.get(currency_pair)

            if fx_rate is None:
                fx_rate = fetch_fx_rate(asset.currency, self.currency)  # pyright: ignore[reportAttributeAccessIssue]
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


class PortfolioTransaction(UUIDModelMixin, TimeStampedModelMixin):
    class TransactionType(models.TextChoices):
        BUY = "buy", "Alım"
        SELL = "sell", "Satış"
        DIVIDEND = "dividend", "Temettü"
        COUPON = "coupon", "Kupon Ödemesi"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
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
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
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
        return f"{self.portfolio} - {self.asset}"

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
    total_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_cost = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    target_value = models.DecimalField(
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_return_pct = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy Snapshot"
        verbose_name_plural = "Portföy Snapshotları"

    def __str__(self) -> str:
        return f"{self.portfolio} - {self.snapshot_date}"

    @classmethod
    def create_snapshot(
        cls,
        *,
        portfolio: Portfolio,
        period: str,
        snapshot_date: timezone.datetime | None = None,
    ) -> "PortfolioSnapshot":
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]

        assets = (
            Asset.objects.filter(transactions__portfolio=portfolio)
            .distinct()
            .order_by("name")
        )
        for asset in assets:
            asset.refresh_price()
            asset.save(
                update_fields=["current_price", "price_updated_at", "updated_at"]
            )

        positions = portfolio.get_positions()
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

        snapshot = cls.objects.create(
            portfolio=portfolio,
            period=period,
            snapshot_date=snapshot_date,
            total_value=total_value,
            total_cost=total_cost,
            target_value=portfolio.target_value,
            total_return_pct=total_return_pct,
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
        max_digits=MAX_DICITS, decimal_places=MAX_DECIMAL_PLACES
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
