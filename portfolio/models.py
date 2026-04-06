from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from core.mixins import SlugMixin, TimeStampedModelMixin, UUIDModelMixin
from core.services.portfolio import (
    build_comparison_name,
    build_snapshot_name,
    format_comparison_label,
    format_snapshot_label,
)
from portfolio.services import (
    calculate_xirr,
    fetch_fx_rate,
    fetch_fx_rates_bulk,
    fetch_multiple_fx_rates_bulk,
    fetch_yahoo_finance_price,
)

MAX_DIGITS = 200
MAX_DECIMAL_PLACES = 8
MAX_DECIMAL_PLACES_FOR_QUANTITY = 5
MAX_DECIMAL_PLACES_FOR_RATE = 8
CACHE_TIMEOUT = 600  # 10 minutes


class BaseSnapshot(SlugMixin, UUIDModelMixin, TimeStampedModelMixin):
    snapshot_date = models.DateField(default=timezone.now)
    name = models.CharField(max_length=200, blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True

    def _get_fallback_name(self) -> str:
        return ""

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.name:
            fallback = self._get_fallback_name()
            if fallback:
                self.name = fallback
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def _prepare_snapshot_data(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> tuple[date, dict[str, object], list[object]]:
        raise NotImplementedError

    @classmethod
    def create_snapshot(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> "BaseSnapshot":
        snapshot_date, snapshot_kwargs, items_data = cls._prepare_snapshot_data(
            snapshot_date=snapshot_date,
            name=name,
            **kwargs,
        )

        snapshot = cls.objects.create(
            snapshot_date=snapshot_date,
            **snapshot_kwargs,
        )

        cls._create_snapshot_items(snapshot, items_data)

        if hasattr(snapshot, "update_irr"):
            snapshot.update_irr()  # pyright: ignore[reportAttributeAccessIssue]

        return snapshot

    @classmethod
    def _create_snapshot_items(
        cls, snapshot: "BaseSnapshot", items_data: list[object]
    ) -> None:
        pass


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
        max_digits=MAX_DIGITS,
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


class PortfolioComparison(SlugMixin, UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
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
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy"
        verbose_name_plural = "Portföyler"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name}"

    @staticmethod
    def _calculate_capital_increase_quantity(
        *,
        current_quantity: Decimal,
        increase_rate_pct: Decimal | None,
    ) -> Decimal:
        if current_quantity <= 0 or not increase_rate_pct or increase_rate_pct <= 0:
            return Decimal("0")
        return current_quantity * increase_rate_pct / Decimal("100")

    def _get_or_fetch_fx_rate(
        self,
        fx_rates: dict[tuple[str, str, date | None], Decimal],
        base_currency: str,
        target_currency: str,
        rate_date: date | None,
    ) -> Decimal:
        currency_pair = (base_currency, target_currency, rate_date)
        if currency_pair not in fx_rates:
            cache_key = f"fx_rate_{base_currency}_{target_currency}_{rate_date.isoformat() if rate_date else 'latest'}"
            cached_rate = cache.get(cache_key)
            if cached_rate is not None:
                fx_rates[currency_pair] = cached_rate
                return cached_rate

            fx_rate = fetch_fx_rate(
                base_currency,
                target_currency,
                rate_date=rate_date,
            )
            final_rate = fx_rate if fx_rate is not None else Decimal("1")
            fx_rates[currency_pair] = final_rate
            cache.set(
                cache_key,
                final_rate,
                timeout=getattr(settings, "CACHE_TIMEOUT", CACHE_TIMEOUT),
            )

        return fx_rates[currency_pair]

    def _get_cache_keys_for_transactions(
        self,
        transactions: list["PortfolioTransaction"],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
        price_date: date | None,
    ) -> dict[str, tuple[tuple[str, str, date | None], date | None, str]]:
        cache_keys: dict[
            str, tuple[tuple[str, str, date | None], date | None, str]
        ] = {}

        for tx in transactions:
            conversion_date = price_date or tx.trade_date
            if tx.asset.currency == self.currency:
                continue
            currency_pair = (tx.asset.currency, self.currency, conversion_date)
            if currency_pair not in fx_rates:
                cache_key = f"fx_rate_{tx.asset.currency}_{self.currency}_{conversion_date.isoformat() if conversion_date else 'latest'}"
                cache_keys[cache_key] = (
                    currency_pair,
                    conversion_date,
                    tx.asset.currency,
                )
        return cache_keys

    def _process_cached_rates(
        self,
        cache_keys: dict[str, tuple[tuple[str, str, date | None], date | None, str]],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
    ) -> dict[date | None, set[tuple[str, str]]]:
        uncached_pairs_by_date: dict[date | None, set[tuple[str, str]]] = {}
        if not cache_keys:
            return uncached_pairs_by_date

        cached_rates = cache.get_many(list(cache_keys.keys()))
        for cache_key, (
            currency_pair,
            conversion_date,
            asset_currency,
        ) in cache_keys.items():
            cached_rate = cached_rates.get(cache_key)
            if cached_rate is not None:
                fx_rates[currency_pair] = cached_rate  # pyright: ignore[reportArgumentType]
            else:
                if conversion_date not in uncached_pairs_by_date:
                    uncached_pairs_by_date[conversion_date] = set()
                uncached_pairs_by_date[conversion_date].add(
                    (asset_currency, self.currency)
                )
        return uncached_pairs_by_date

    def _fetch_and_cache_missing_rates(
        self,
        uncached_pairs_by_date: dict[date | None, set[tuple[str, str]]],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
    ) -> None:
        if not uncached_pairs_by_date:
            return

        fetched_rates = fetch_multiple_fx_rates_bulk(uncached_pairs_by_date)
        for rate_date, pairs in uncached_pairs_by_date.items():
            for pair in pairs:
                currency_pair = (pair[0], pair[1], rate_date)
                cache_key = f"fx_rate_{pair[0]}_{pair[1]}_{rate_date.isoformat() if rate_date else 'latest'}"
                fx_rate = fetched_rates.get(currency_pair, Decimal("1"))  # pyright: ignore
                cache.set(
                    cache_key,
                    fx_rate,
                    timeout=getattr(settings, "CACHE_TIMEOUT", CACHE_TIMEOUT),
                )
                fx_rates[currency_pair] = fx_rate  # pyright: ignore[reportArgumentType]

    def _prefetch_fx_rates(
        self,
        transactions: list["PortfolioTransaction"],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
        price_date: date | None = None,
    ) -> None:
        cache_keys = self._get_cache_keys_for_transactions(
            transactions, fx_rates, price_date
        )
        uncached_pairs_by_date = self._process_cached_rates(cache_keys, fx_rates)
        self._fetch_and_cache_missing_rates(uncached_pairs_by_date, fx_rates)

    @staticmethod
    def _apply_buy(
        transaction: "PortfolioTransaction",
        quantity: Decimal,
        cost_basis: Decimal,
        value_adjustment: Decimal,
        fx_rate: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        transaction_cost = transaction.total_cost * fx_rate
        return (
            quantity + transaction.quantity,
            cost_basis + transaction_cost,
            value_adjustment,
        )

    @staticmethod
    def _apply_bonus_capital_increase(
        increase_quantity: Decimal,
        quantity: Decimal,
        cost_basis: Decimal,
        value_adjustment: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        return quantity + increase_quantity, cost_basis, value_adjustment

    @staticmethod
    def _apply_rights_exercised(
        transaction: "PortfolioTransaction",
        increase_quantity: Decimal,
        quantity: Decimal,
        cost_basis: Decimal,
        value_adjustment: Decimal,
        fx_rate: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        rights_cost = increase_quantity * transaction.price_per_unit * fx_rate
        return quantity + increase_quantity, cost_basis + rights_cost, value_adjustment

    @staticmethod
    def _apply_rights_not_exercised(
        transaction: "PortfolioTransaction",
        increase_quantity: Decimal,
        quantity: Decimal,
        cost_basis: Decimal,
        value_adjustment: Decimal,
        fx_rate: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        rights_loss = increase_quantity * transaction.price_per_unit * fx_rate
        return quantity, cost_basis, value_adjustment - rights_loss

    @staticmethod
    def _apply_sell(
        transaction: "PortfolioTransaction",
        quantity: Decimal,
        cost_basis: Decimal,
        value_adjustment: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        if quantity > 0:
            average_cost = cost_basis / quantity
            cost_basis -= average_cost * transaction.quantity
        quantity -= transaction.quantity
        return quantity, cost_basis, value_adjustment

    def _apply_transaction_to_position(
        self,
        transaction: "PortfolioTransaction",
        data: dict[str, Decimal | Asset],
        fx_rate: Decimal,
    ) -> None:
        quantity = data["quantity"]
        cost_basis = data["cost_basis"]
        value_adjustment = data["value_adjustment"]

        assert isinstance(quantity, Decimal)
        assert isinstance(cost_basis, Decimal)
        assert isinstance(value_adjustment, Decimal)

        increase_quantity = self._calculate_capital_increase_quantity(
            current_quantity=quantity,
            increase_rate_pct=transaction.capital_increase_rate_pct,
        )

        if transaction.transaction_type == PortfolioTransaction.TransactionType.BUY:
            quantity, cost_basis, value_adjustment = self._apply_buy(
                transaction, quantity, cost_basis, value_adjustment, fx_rate
            )
        elif (
            transaction.transaction_type
            == PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE
        ):
            quantity, cost_basis, value_adjustment = self._apply_bonus_capital_increase(
                increase_quantity, quantity, cost_basis, value_adjustment
            )
        elif (
            transaction.transaction_type
            == PortfolioTransaction.TransactionType.RIGHTS_EXERCISED
        ):
            quantity, cost_basis, value_adjustment = self._apply_rights_exercised(
                transaction,
                increase_quantity,
                quantity,
                cost_basis,
                value_adjustment,
                fx_rate,
            )
        elif (
            transaction.transaction_type
            == PortfolioTransaction.TransactionType.RIGHTS_NOT_EXERCISED
        ):
            quantity, cost_basis, value_adjustment = self._apply_rights_not_exercised(
                transaction,
                increase_quantity,
                quantity,
                cost_basis,
                value_adjustment,
                fx_rate,
            )
        elif transaction.transaction_type == PortfolioTransaction.TransactionType.SELL:
            quantity, cost_basis, value_adjustment = self._apply_sell(
                transaction, quantity, cost_basis, value_adjustment
            )

        if quantity <= 0:
            quantity = Decimal("0")
            cost_basis = Decimal("0")
            value_adjustment = Decimal("0")

        data["quantity"] = quantity
        data["cost_basis"] = cost_basis
        data["value_adjustment"] = value_adjustment

    def _build_initial_positions(
        self,
        transactions: list["PortfolioTransaction"] | QuerySet["PortfolioTransaction"],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
        price_date: date | None,
    ) -> dict[str, dict[str, Decimal | Asset]]:
        positions: dict[str, dict[str, Decimal | Asset]] = {}

        tx_list = list(transactions)
        self._prefetch_fx_rates(tx_list, fx_rates, price_date)

        for transaction in tx_list:
            asset = transaction.asset
            conversion_date = price_date or transaction.trade_date
            fx_rate = self._get_or_fetch_fx_rate(
                fx_rates, asset.currency, self.currency, conversion_date
            )
            data = positions.setdefault(
                str(asset.id),
                {
                    "asset": asset,
                    "quantity": Decimal("0"),
                    "cost_basis": Decimal("0"),
                    "value_adjustment": Decimal("0"),
                },
            )
            self._apply_transaction_to_position(transaction, data, fx_rate)

        return positions

    def _get_asset_current_price(
        self,
        asset: "Asset",
        price_date: date | None,
    ) -> Decimal:
        current_price = asset.current_price or Decimal("0")  # pyright: ignore[reportAttributeAccessIssue]
        if not asset.symbol:  # pyright: ignore[reportAttributeAccessIssue]
            return current_price

        cache_key = f"yf_price_{asset.symbol}_{price_date.isoformat() if price_date else 'latest'}"
        cached_price = cache.get(cache_key)
        if cached_price is not None:
            return cached_price

        fetched_price = None
        if price_date:
            fetched_price = fetch_yahoo_finance_price(
                asset.symbol,  # pyright: ignore[reportAttributeAccessIssue]
                price_date=price_date,
            )
        elif not current_price:
            fetched_price = fetch_yahoo_finance_price(asset.symbol)  # pyright: ignore[reportAttributeAccessIssue]

        if fetched_price is not None:
            current_price = fetched_price
            cache.set(
                cache_key,
                current_price,
                timeout=getattr(settings, "CACHE_TIMEOUT", CACHE_TIMEOUT),
            )

        return current_price

    def _update_market_values(
        self,
        positions: dict[str, dict[str, Decimal | Asset]],
        fx_rates: dict[tuple[str, str, date | None], Decimal],
        price_date: date | None,
    ) -> Decimal:
        total_value = Decimal("0")
        for data in positions.values():
            asset = data["asset"]
            quantity = data["quantity"]
            current_price = self._get_asset_current_price(asset, price_date)  # pyright: ignore[reportArgumentType]
            fx_rate = self._get_or_fetch_fx_rate(
                fx_rates,
                asset.currency,  # pyright: ignore[reportAttributeAccessIssue]
                self.currency,
                price_date,  # pyright: ignore[reportAttributeAccessIssue]
            )

            converted_price = current_price * fx_rate
            data["current_price"] = converted_price
            if asset.asset_type == Asset.AssetType.BES:  # pyright: ignore[reportAttributeAccessIssue]
                data["market_value"] = (
                    converted_price + data["value_adjustment"]  # pyright: ignore[reportOperatorIssue]
                )
            else:
                data["market_value"] = (
                    quantity * converted_price + data["value_adjustment"]  # pyright: ignore[reportOperatorIssue]
                )

            total_value += data["market_value"]
        return total_value

    def _update_position_metrics(
        self,
        positions: dict[str, dict[str, Decimal | Asset]],
        total_value: Decimal,
    ) -> None:
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

    def _get_filtered_transactions(
        self, price_date: date | None
    ) -> list["PortfolioTransaction"] | QuerySet["PortfolioTransaction"]:
        if (
            hasattr(self, "_prefetched_objects_cache")
            and "transactions" in self._prefetched_objects_cache  # pyright: ignore[reportAttributeAccessIssue]
        ):
            tx_list = [
                tx
                for tx in self.transactions.all()  # pyright: ignore[reportAttributeAccessIssue]
                if not price_date or tx.trade_date <= price_date
            ]
            tx_list.sort(key=lambda tx: (tx.trade_date, tx.created_at))

            if tx_list and "asset" not in tx_list[0]._state.fields_cache:
                from django.db.models import prefetch_related_objects

                prefetch_related_objects(tx_list, "asset")

            return tx_list

        transactions = (
            self.transactions.select_related(  # pyright: ignore[reportAttributeAccessIssue]
                "asset"
            )
            .order_by("trade_date", "created_at")
            .distinct()
        )
        if price_date:
            transactions = transactions.filter(trade_date__lte=price_date)
        return transactions

    def get_positions(
        self,
        *,
        price_date: date | None = None,
    ) -> list[dict[str, Decimal | Asset]]:
        transactions = self._get_filtered_transactions(price_date)
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}

        positions = self._build_initial_positions(transactions, fx_rates, price_date)
        total_value = self._update_market_values(positions, fx_rates, price_date)
        self._update_position_metrics(positions, total_value)

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

    def _build_irr_cash_flows(
        self,
        transactions: list["PortfolioTransaction"] | QuerySet["PortfolioTransaction"],
    ) -> list[tuple[date, Decimal]]:
        tx_cash_flows = []
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        asset_quantities: dict[str, Decimal] = {}

        self._prefetch_fx_rates(transactions, fx_rates)  # pyright: ignore[reportArgumentType]

        for tx in transactions:
            fx_rate = self._get_or_fetch_fx_rate(
                fx_rates, tx.asset.currency, self.currency, tx.trade_date
            )

            asset_id_str = str(tx.asset_id)  # pyright: ignore[reportAttributeAccessIssue]
            current_quantity = asset_quantities.get(asset_id_str, Decimal("0"))

            rights_quantity = self._calculate_capital_increase_quantity(
                current_quantity=current_quantity,
                increase_rate_pct=tx.capital_increase_rate_pct,
            )
            amount = tx.total_cost * fx_rate
            if tx.transaction_type == PortfolioTransaction.TransactionType.BUY:
                tx_cash_flows.append((tx.trade_date, -amount))
            elif (
                tx.transaction_type
                == PortfolioTransaction.TransactionType.RIGHTS_EXERCISED
            ):
                rights_cost = rights_quantity * tx.price_per_unit * fx_rate
                tx_cash_flows.append((tx.trade_date, -rights_cost))
            elif tx.transaction_type == PortfolioTransaction.TransactionType.SELL:
                tx_cash_flows.append((tx.trade_date, amount))

            if tx.transaction_type == PortfolioTransaction.TransactionType.BUY:
                current_quantity += tx.quantity
            elif tx.transaction_type == PortfolioTransaction.TransactionType.SELL:
                current_quantity -= tx.quantity
            elif tx.transaction_type in (
                PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
                PortfolioTransaction.TransactionType.RIGHTS_EXERCISED,
            ):
                current_quantity += rights_quantity

            if current_quantity < 0:
                current_quantity = Decimal("0")

            asset_quantities[asset_id_str] = current_quantity

        return tx_cash_flows

    def calculate_irr(self, as_of_date: date, current_value: Decimal) -> Decimal | None:
        """
        Calculates the Internal Rate of Return (IRR) for the portfolio as of a given date
        and current market value.
        """
        tx_list = self._get_filtered_transactions(as_of_date)
        tx_cash_flows = self._build_irr_cash_flows(tx_list)

        tx_cash_flows.append((as_of_date, current_value))
        irr = calculate_xirr(tx_cash_flows)
        return Decimal(str(irr)) * 100 if irr is not None else None

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
        BONUS_CAPITAL_INCREASE = "bonus_ci", "Bedelsiz Sermaye Artırımı"
        RIGHTS_EXERCISED = "rights_use", "Bedelli (Rüçhan Kullanıldı)"
        RIGHTS_NOT_EXERCISED = "rights_skip", "Bedelli (Rüçhan Kullanılmadı)"

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
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.BUY,
    )
    trade_date = models.DateField()
    quantity = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    capital_increase_rate_pct = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=MAX_DECIMAL_PLACES_FOR_RATE,
        null=True,
        blank=True,
        help_text=(
            "transaction_type: Bedelsiz Sermaye Artırımı<br>\n"
            "capital_increase_rate_pct: 900<br>\n"
            "quantity: 0 (bu akışta oran üzerinden otomatik hesaplandığı için manuel lot girmiyorsunuz)<br>\n"
            "price_per_unit: 0 (bedelsiz olduğu için)<br>\n"
            "trade_date: bedelsizin gerçekleştiği tarih<br>\n"
            "asset / portfolios: ilgili X varlığı ve portföyünüz<br>\n"
            "---<br>\n"
            "transaction_type: Bedelli (Rüçhan Kullanılmadı)<br>\n"
            "capital_increase_rate_pct: 500<br>\n"
            "quantity: 0 (oran bazlı sistemde bu alan bu tip işlemde kullanılmıyor)<br>\n"
            "price_per_unit: şirketin bedelli/rüçhan kullanım fiyatı (örn. 15 TL, 20 TL vb.)<br>\n"
            "trade_date: bedelli tarihi<br>\n"
            "asset / portfolios: ilgili X varlığı ve portföyünüz<br>\n"
            "---<br>\n"
            "transaction_type: Bedelli (Rüçhan Kullanıldı)<br>\n"
            "capital_increase_rate_pct: 500<br>\n"
            "quantity: 0 (bu akışta adet oranla arka planda hesaplanıyor)<br>\n"
            "price_per_unit: bedelliye katılım birim fiyatı (şirketin açıkladığı rüçhan kullanım fiyatı)<br>\n"
            "trade_date: bedelli tarihi<br>\n"
            "asset / portfolios: ilgili X varlığı ve portföyünüz<br>\n"
        ),
    )
    price_per_unit = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )

    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Portföy İşlemi"
        verbose_name_plural = "Portföy İşlemleri"

    def clean(self) -> None:
        super().clean()
        requires_rate = self.transaction_type in (
            self.TransactionType.BONUS_CAPITAL_INCREASE,
            self.TransactionType.RIGHTS_EXERCISED,
            self.TransactionType.RIGHTS_NOT_EXERCISED,
        )
        if requires_rate and (
            self.capital_increase_rate_pct is None
            or self.capital_increase_rate_pct <= 0
        ):
            raise ValidationError(
                {
                    "capital_increase_rate_pct": "Sermaye artırımı oranı 0'dan büyük olmalıdır."
                }
            )

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


class PortfolioSnapshot(BaseSnapshot):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Aylık"
        YEARLY = "yearly", "Yıllık"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    period = models.CharField(max_length=10, choices=Period.choices)
    total_value = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_cost = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    target_value = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_return_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    irr_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES, null=True, blank=True
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

    def _get_fallback_name(self) -> str:
        if self.portfolio_id and self.snapshot_date:  # pyright: ignore[reportAttributeAccessIssue]
            return build_snapshot_name(f"{self.portfolio}", self.snapshot_date)
        return ""

    def update_irr(self) -> Decimal | None:
        """
        Calculates and updates the irr_pct for this snapshot.
        """
        has_earlier_snapshot = self.__class__.objects.filter(
            portfolio=self.portfolio,
            snapshot_date__lt=self.snapshot_date,
        ).exists()
        has_same_day_earlier_snapshot = False
        if not has_earlier_snapshot and self.pk:
            has_same_day_earlier_snapshot = (
                self.__class__.objects.filter(
                    portfolio=self.portfolio,
                    snapshot_date=self.snapshot_date,
                    created_at__lt=self.created_at,
                )
                .exclude(pk=self.pk)
                .exists()
            )

        if not has_earlier_snapshot and not has_same_day_earlier_snapshot:
            self.irr_pct = None
            self.save(update_fields=["irr_pct", "updated_at"])
            return self.irr_pct

        self.irr_pct = self.portfolio.calculate_irr(
            as_of_date=self.snapshot_date,
            current_value=self.total_value,
        )
        self.save(update_fields=["irr_pct", "updated_at"])
        return self.irr_pct

    @classmethod
    def _prepare_snapshot_data(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> tuple[date, dict[str, object], list[object]]:
        portfolio = kwargs["portfolio"]
        period = kwargs["period"]
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]

        positions = portfolio.get_positions(price_date=snapshot_date)  # pyright: ignore[reportAttributeAccessIssue]
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

        snapshot_kwargs = {
            "portfolio": portfolio,
            "period": period,
            "name": name or "",
            "total_value": total_value,
            "total_cost": total_cost,
            "target_value": portfolio.target_value,  # pyright: ignore[reportAttributeAccessIssue]
            "total_return_pct": total_return_pct,
        }
        return snapshot_date, snapshot_kwargs, list(positions)

    @classmethod
    def _create_snapshot_items(
        cls, snapshot: BaseSnapshot, items_data: list[object]
    ) -> None:
        items = [
            PortfolioSnapshotItem(
                snapshot=snapshot,
                asset=position["asset"],  # pyright: ignore[reportIndexIssue]
                quantity=position["quantity"],  # pyright: ignore[reportIndexIssue]
                average_cost=position["average_cost"],  # pyright: ignore[reportIndexIssue]
                cost_basis=position["cost_basis"],  # pyright: ignore[reportIndexIssue]
                current_price=position["current_price"],  # pyright: ignore[reportIndexIssue]
                market_value=position["market_value"],  # pyright: ignore[reportIndexIssue]
                allocation_pct=position["allocation_pct"],  # pyright: ignore[reportIndexIssue]
                gain_loss=position["gain_loss"],  # pyright: ignore[reportIndexIssue]
                gain_loss_pct=position["gain_loss_pct"],  # pyright: ignore[reportIndexIssue]
            )
            for position in items_data
        ]
        if items:
            PortfolioSnapshotItem.objects.bulk_create(items)


class PortfolioSnapshotItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        PortfolioSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    quantity = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    average_cost = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    cost_basis = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    current_price = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    market_value = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_RATE
    )
    gain_loss = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    gain_loss_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_RATE
    )

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
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
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


class CashFlowSnapshot(BaseSnapshot):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Aylık"
        YEARLY = "yearly", "Yıllık"

    cashflow = models.ForeignKey(
        CashFlow,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    period = models.CharField(max_length=10, choices=Period.choices)
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="İsimlendirme yapılmazsa CashFlow adı kullanılır.",
    )
    total_amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
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

    def _get_fallback_name(self) -> str:
        if self.cashflow_id:  # pyright: ignore[reportAttributeAccessIssue]
            return build_snapshot_name(f"{self.cashflow}", self.snapshot_date)
        return ""

    @classmethod
    def _get_date_range(cls, snapshot_date: date, period: str) -> tuple[date, date]:
        if period == cls.Period.MONTHLY:
            start_date = snapshot_date.replace(day=1)
            last_day = calendar.monthrange(snapshot_date.year, snapshot_date.month)[1]
            end_date = snapshot_date.replace(day=last_day)
        else:
            start_date = snapshot_date.replace(month=1, day=1)
            end_date = snapshot_date.replace(month=12, day=31)
        if snapshot_date < end_date:
            end_date = snapshot_date
        return start_date, end_date

    @classmethod
    def _get_entries(
        cls, cashflow: CashFlow, start_date: date, end_date: date
    ) -> QuerySet:
        return CashFlowEntry.objects.filter(  # pyright: ignore[reportReturnType]
            cashflows=cashflow,
            entry_date__gte=start_date,
            entry_date__lte=end_date,
        ).values("category", "amount", "currency", "entry_date")

    @classmethod
    def _get_fx_rates(
        cls,
        entries: QuerySet,
        base_currency: str,
        snapshot_date: date,
    ) -> dict[tuple[str, str, date | None], Decimal]:
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        unique_currencies = {
            entry["currency"] for entry in entries if entry["currency"] != base_currency
        }

        uncached_pairs = []
        cache_keys = {}

        for entry_currency in unique_currencies:
            currency_pair = (entry_currency, base_currency, snapshot_date)
            cache_key = (
                f"fx_rate_{entry_currency}_{base_currency}_{snapshot_date.isoformat()}"
            )
            cache_keys[cache_key] = (entry_currency, currency_pair)

        if cache_keys:
            cached_rates = cache.get_many(list(cache_keys.keys()))
            for cache_key, (entry_currency, currency_pair) in cache_keys.items():
                cached_rate = cached_rates.get(cache_key)
                if cached_rate is not None:
                    fx_rates[currency_pair] = cached_rate  # pyright: ignore[reportArgumentType]
                else:
                    uncached_pairs.append((entry_currency, base_currency))

        if uncached_pairs:
            fetched_rates = fetch_fx_rates_bulk(uncached_pairs, rate_date=snapshot_date)
            for pair in uncached_pairs:
                currency_pair = (pair[0], pair[1], snapshot_date)
                cache_key = f"fx_rate_{pair[0]}_{pair[1]}_{snapshot_date.isoformat()}"
                fx_rate = (fetched_rates or {}).get(pair, Decimal("1"))
                cache.set(
                    cache_key,
                    fx_rate,
                    timeout=getattr(settings, "CACHE_TIMEOUT", CACHE_TIMEOUT),
                )
                fx_rates[currency_pair] = fx_rate  # pyright: ignore[reportArgumentType]

        return fx_rates

    @classmethod
    def _calculate_category_totals(
        cls,
        entries: QuerySet,
        cashflow_currency: str,
        snapshot_date: date,
        fx_rates: dict[tuple[str, str, date | None], Decimal],
    ) -> dict[str, Decimal]:
        category_totals: dict[str, Decimal] = {}
        for entry in entries:
            amount = entry["amount"] or Decimal("0")
            entry_currency = entry["currency"]
            fx_rate = Decimal("1")
            if entry_currency != cashflow_currency:
                currency_pair = (entry_currency, cashflow_currency, snapshot_date)
                fx_rate = fx_rates.get(currency_pair, Decimal("1"))
            converted_amount = amount * fx_rate
            category_totals[entry["category"]] = (
                category_totals.get(entry["category"], Decimal("0")) + converted_amount
            )
        return category_totals

    @classmethod
    def _build_items_data(
        cls, category_totals: dict[str, Decimal], total_amount: Decimal
    ) -> list[dict[str, object]]:
        items_data = []
        for category, amount in sorted(category_totals.items()):
            allocation_pct = amount / total_amount if total_amount > 0 else Decimal("0")
            items_data.append(
                {
                    "category": category,
                    "amount": amount,
                    "allocation_pct": allocation_pct,
                }
            )
        return items_data

    @classmethod
    def _prepare_snapshot_data(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> tuple[date, dict[str, object], list[object]]:
        cashflow = kwargs["cashflow"]
        period = kwargs["period"]
        snapshot_date = snapshot_date or timezone.now().date()  # pyright: ignore[reportAssignmentType]

        start_date, end_date = cls._get_date_range(snapshot_date, period)  # pyright: ignore[reportArgumentType]

        entries = cls._get_entries(cashflow, start_date, end_date)  # pyright: ignore[reportArgumentType]

        fx_rates = cls._get_fx_rates(
            entries,  # pyright: ignore[reportArgumentType]
            cashflow.currency,  # pyright: ignore[reportAttributeAccessIssue]
            snapshot_date,
        )

        category_totals = cls._calculate_category_totals(
            entries,  # pyright: ignore[reportArgumentType]
            cashflow.currency,  # pyright: ignore[reportAttributeAccessIssue]
            snapshot_date,
            fx_rates,
        )

        total_amount = sum(category_totals.values(), Decimal("0"))

        snapshot_kwargs = {
            "cashflow": cashflow,
            "period": period,
            "total_amount": total_amount,
            "name": name or cashflow.name,  # pyright: ignore[reportAttributeAccessIssue]
        }
        items_data = cls._build_items_data(category_totals, total_amount)

        return snapshot_date, snapshot_kwargs, items_data  # pyright: ignore[reportReturnType]

    @classmethod
    def _create_snapshot_items(
        cls, snapshot: BaseSnapshot, items_data: list[object]
    ) -> None:
        objects_to_create = [
            CashFlowSnapshotItem(
                snapshot=snapshot,
                category=item["category"],  # pyright: ignore[reportIndexIssue]
                amount=item["amount"],  # pyright: ignore[reportIndexIssue]
                allocation_pct=item["allocation_pct"],  # pyright: ignore[reportIndexIssue]
            )
            for item in items_data
        ]
        if objects_to_create:
            CashFlowSnapshotItem.objects.bulk_create(objects_to_create)


class CashFlowSnapshotItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        CashFlowSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.CharField(max_length=30, choices=CashFlowEntry.Category.choices)
    amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_RATE
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Nakit Akışı Snapshot Kalemi"
        verbose_name_plural = "Nakit Akışı Snapshot Kalemleri"

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.get_category_display()}"  # pyright: ignore[reportAttributeAccessIssue]


class CashFlowComparison(SlugMixin, UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
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
        max_digits=MAX_DIGITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    savings_amount = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    notes = models.TextField(blank=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Maaş/Tasarruf Girişi"
        verbose_name_plural = "Maaş/Tasarruf Girişleri"
        ordering = ("-entry_date", "-created_at")

    def __str__(self) -> str:
        return f"{self.flow} - {self.entry_date}"


class SalarySavingsSnapshot(BaseSnapshot):
    flow = models.ForeignKey(
        SalarySavingsFlow,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="İsimlendirme yapılmazsa akış adı ve tarih kullanılır.",
    )
    total_salary = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    total_savings = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=MAX_DECIMAL_PLACES,
    )
    savings_rate = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_RATE
    )

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

    def _get_fallback_name(self) -> str:
        if self.flow_id:  # pyright: ignore[reportAttributeAccessIssue]
            return build_snapshot_name(f"{self.flow}", self.snapshot_date)
        return ""

    @classmethod
    def _prepare_snapshot_data(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> tuple[date, dict[str, object], list[object]]:
        flow = kwargs["flow"]
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

        snapshot_kwargs = {
            "flow": flow,
            "name": name or "",
            "total_salary": total_salary,
            "total_savings": total_savings,
            "savings_rate": savings_rate,
        }
        return snapshot_date, snapshot_kwargs, []


class DividendComparison(SlugMixin, UUIDModelMixin, TimeStampedModelMixin):
    name = models.CharField(max_length=255, blank=True)
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
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]


class DividendPayment(UUIDModelMixin, TimeStampedModelMixin):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="dividend_payments",
    )
    payment_date = models.DateField()
    share_count = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_QUANTITY
    )
    net_dividend_per_share = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    average_cost = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    last_close_price = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
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
        dividends_to_create_or_update = []
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
            dividends_to_create_or_update.append(
                Dividend(
                    payment=self,
                    currency=currency,
                    per_share_net_amount=per_share,
                    total_net_amount=total_converted,
                )
            )

        if dividends_to_create_or_update:
            Dividend.objects.bulk_create(
                dividends_to_create_or_update,
                update_conflicts=True,
                unique_fields=["payment", "currency"],
                update_fields=["per_share_net_amount", "total_net_amount"],
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
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_net_amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
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


class DividendSnapshot(BaseSnapshot):
    year = models.PositiveIntegerField()
    currency = models.CharField(
        max_length=10,
        choices=Asset.Currency.choices,
        default=Asset.Currency.TRY,
    )
    total_amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Snapshot"
        verbose_name_plural = "Temettü Snapshotları"
        ordering = ("-snapshot_date", "-created_at")

    def __str__(self) -> str:
        if self.slug:
            return self.slug
        return self.name or f"{self.year} Temettü"

    def _get_fallback_name(self) -> str:
        if self.year:
            return f"{self.year} Temettü Özeti"
        return ""

    @classmethod
    def _get_fx_rates(
        cls,
        payments: QuerySet,  # pyright: ignore[reportMissingTypeArgument]
        target_currency: str,
        snapshot_date: date,
    ) -> dict[tuple[str, str, date | None], Decimal]:
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}

        unique_currencies = {
            payment.asset.currency
            for payment in payments
            if payment.asset.currency != target_currency
        }

        uncached_pairs = []
        cache_keys = {}

        for entry_currency in unique_currencies:
            currency_pair = (entry_currency, target_currency, snapshot_date)
            cache_key = f"fx_rate_{entry_currency}_{target_currency}_{snapshot_date.isoformat() if snapshot_date else 'latest'}"
            cache_keys[cache_key] = (entry_currency, currency_pair)

        if cache_keys:
            cached_rates = cache.get_many(list(cache_keys.keys()))
            for cache_key, (entry_currency, currency_pair) in cache_keys.items():
                cached_rate = cached_rates.get(cache_key)
                if cached_rate is not None:
                    fx_rates[currency_pair] = cached_rate  # pyright: ignore[reportArgumentType]
                else:
                    uncached_pairs.append((entry_currency, target_currency))

        if uncached_pairs:
            fetched_rates = fetch_fx_rates_bulk(uncached_pairs, rate_date=snapshot_date)
            for pair in uncached_pairs:
                currency_pair = (pair[0], pair[1], snapshot_date)
                cache_key = f"fx_rate_{pair[0]}_{pair[1]}_{snapshot_date.isoformat() if snapshot_date else 'latest'}"
                fx_rate = (fetched_rates or {}).get(pair, Decimal("1"))
                cache.set(
                    cache_key,
                    fx_rate,
                    timeout=getattr(settings, "CACHE_TIMEOUT", CACHE_TIMEOUT),
                )
                fx_rates[currency_pair] = fx_rate  # pyright: ignore[reportArgumentType]

        return fx_rates

    @classmethod
    def _build_items_data(
        cls,
        asset_totals: dict[str, dict[str, object]],
        payment_rows: list[dict[str, object]],
        total_amount: Decimal,
    ) -> list[object]:
        items_data: list[object] = []
        for asset_entry in asset_totals.values():
            amount = asset_entry["total_amount"]  # pyright: ignore[reportAssignmentType]
            allocation_pct = amount / total_amount if total_amount > 0 else Decimal("0")  # pyright: ignore[reportOperatorIssue]
            items_data.append(
                {
                    "type": "asset",
                    "asset": asset_entry["asset"],
                    "total_amount": amount,
                    "allocation_pct": allocation_pct,
                }
            )

        for row in payment_rows:
            items_data.append(
                {
                    "type": "payment",
                    "asset": row["asset"],
                    "payment": row["payment"],
                    "payment_date": row["payment_date"],
                    "per_share_net_amount": row["per_share_net_amount"],
                    "dividend_yield_on_payment_price": row[
                        "dividend_yield_on_payment_price"
                    ],
                    "dividend_yield_on_average_cost": row[
                        "dividend_yield_on_average_cost"
                    ],
                    "total_net_amount": row["total_net_amount"],
                }
            )
        return items_data

    @classmethod
    def _get_dividends_map(
        cls, payments_list: list[DividendPayment], currency: str
    ) -> dict[str, Dividend]:
        unprefetched_ids = [
            p.id
            for p in payments_list
            if not (
                hasattr(p, "_prefetched_objects_cache")
                and "dividends" in p._prefetched_objects_cache  # pyright: ignore[reportAttributeAccessIssue]
            )
        ]

        dividends_map = {}
        if unprefetched_ids:
            from portfolio.models import Dividend

            dividends_map = {
                d.payment_id: d  # pyright: ignore[reportAttributeAccessIssue]
                for d in Dividend.objects.filter(
                    payment_id__in=unprefetched_ids, currency=currency
                ).iterator()
            }
        return dividends_map

    @classmethod
    def _calculate_payment_amounts(
        cls,
        payment: DividendPayment,
        dividend: Dividend | None,
        currency: str,
        snapshot_date: date,
        fx_rates: dict[tuple[str, str, date | None], Decimal],
    ) -> tuple[Decimal, Decimal]:
        if dividend:
            per_share = dividend.per_share_net_amount
            total_payment = dividend.total_net_amount
        else:
            fx_rate = Decimal("1")
            if payment.asset.currency != currency:
                currency_pair = (payment.asset.currency, currency, snapshot_date)
                fx_rate = fx_rates.get(currency_pair, Decimal("1"))  # pyright: ignore[reportCallIssue, reportArgumentType]
            per_share = payment.net_dividend_per_share * fx_rate  # pyright: ignore[reportOperatorIssue]
            total_payment = payment.total_net_amount * fx_rate
        return per_share, total_payment

    @classmethod
    def _process_payments(
        cls,
        payments: QuerySet,  # pyright: ignore[reportMissingTypeArgument]
        currency: str,
        snapshot_date: date,
        fx_rates: dict[tuple[str, str, date | None], Decimal],
    ) -> tuple[Decimal, dict[str, dict[str, object]], list[dict[str, object]]]:
        total_amount = Decimal("0")
        asset_totals: dict[str, dict[str, object]] = {}
        payment_rows: list[dict[str, object]] = []

        payments_list = list(payments)
        dividends_map = cls._get_dividends_map(payments_list, currency)

        for payment in payments_list:
            if (
                hasattr(payment, "_prefetched_objects_cache")
                and "dividends" in payment._prefetched_objects_cache
            ):
                dividend = next(
                    (d for d in payment.dividends.all() if d.currency == currency),
                    None,  # pyright: ignore[reportAttributeAccessIssue]
                )
            else:
                dividend = dividends_map.get(payment.id)

            per_share, total_payment = cls._calculate_payment_amounts(
                payment, dividend, currency, snapshot_date, fx_rates
            )

            avg_cost = payment.average_cost
            last_close = payment.last_close_price
            yield_on_payment = (
                payment.net_dividend_per_share / last_close
                if last_close > 0
                else Decimal("0")
            )
            yield_on_average = (
                payment.net_dividend_per_share / avg_cost
                if avg_cost > 0
                else Decimal("0")
            )
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

        return total_amount, asset_totals, payment_rows

    @classmethod
    def _prepare_snapshot_data(
        cls,
        *,
        snapshot_date: date | None = None,
        name: str | None = None,
        **kwargs: object,
    ) -> tuple[date, dict[str, object], list[object]]:
        year = kwargs["year"]
        currency = kwargs["currency"]
        snapshot_date = snapshot_date or date(year, 12, 31)  # pyright: ignore[reportArgumentType]
        payments = (
            DividendPayment.objects.select_related("asset")
            .prefetch_related("dividends")
            .filter(payment_date__year=year, payment_date__lte=snapshot_date)
            .order_by("payment_date", "created_at")
        )

        fx_rates = cls._get_fx_rates(
            payments,
            str(currency),
            snapshot_date,
        )

        total_amount, asset_totals, payment_rows = cls._process_payments(
            payments,
            str(currency),
            snapshot_date,
            fx_rates,
        )

        name_override = name or f"{year} Temettü Özeti"
        snapshot_kwargs = {
            "year": year,
            "currency": currency,
            "total_amount": total_amount,
            "name": name_override,
        }

        items_data = cls._build_items_data(asset_totals, payment_rows, total_amount)

        return snapshot_date, snapshot_kwargs, items_data

    @classmethod
    def _create_snapshot_items(
        cls, snapshot: BaseSnapshot, items_data: list[object]
    ) -> None:
        asset_items = []
        payment_items = []
        for item in items_data:
            item_type = item["type"]  # pyright: ignore[reportIndexIssue]
            if item_type == "asset":
                asset_items.append(
                    DividendSnapshotAssetItem(
                        snapshot=snapshot,
                        asset=item["asset"],  # pyright: ignore[reportIndexIssue]
                        total_amount=item["total_amount"],  # pyright: ignore[reportIndexIssue]
                        allocation_pct=item["allocation_pct"],  # pyright: ignore[reportIndexIssue]
                    )
                )
            elif item_type == "payment":
                payment_items.append(
                    DividendSnapshotPaymentItem(
                        snapshot=snapshot,
                        asset=item["asset"],  # pyright: ignore[reportIndexIssue]
                        payment=item["payment"],  # pyright: ignore[reportIndexIssue]
                        payment_date=item["payment_date"],  # pyright: ignore[reportIndexIssue]
                        per_share_net_amount=item["per_share_net_amount"],  # pyright: ignore[reportIndexIssue]
                        dividend_yield_on_payment_price=item[  # pyright: ignore[reportIndexIssue]
                            "dividend_yield_on_payment_price"
                        ],  # pyright: ignore[reportIndexIssue]
                        dividend_yield_on_average_cost=item[  # pyright: ignore[reportIndexIssue]
                            "dividend_yield_on_average_cost"
                        ],  # pyright: ignore[reportIndexIssue]
                        total_net_amount=item["total_net_amount"],  # pyright: ignore[reportIndexIssue]
                    )
                )

        if asset_items:
            DividendSnapshotAssetItem.objects.bulk_create(asset_items)
        if payment_items:
            DividendSnapshotPaymentItem.objects.bulk_create(payment_items)


class DividendSnapshotAssetItem(UUIDModelMixin, TimeStampedModelMixin):
    snapshot = models.ForeignKey(
        DividendSnapshot,
        on_delete=models.CASCADE,
        related_name="asset_items",
    )
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    total_amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    allocation_pct = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES_FOR_RATE
    )

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
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    dividend_yield_on_payment_price = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    dividend_yield_on_average_cost = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )
    total_net_amount = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=MAX_DECIMAL_PLACES
    )

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = "Temettü Snapshot Ödeme Kalemi"
        verbose_name_plural = "Temettü Snapshot Ödeme Kalemleri"
        ordering = ("payment_date", "created_at")

    def __str__(self) -> str:
        return f"{self.snapshot} - {self.asset} - {self.payment_date}"
