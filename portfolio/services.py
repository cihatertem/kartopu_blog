from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import yfinance as yf

from core.decorators import log_exceptions


def calculate_xirr(cash_flows: list[tuple[date, Decimal]]) -> float | None:
    """
    Calculates the Internal Rate of Return for a series of cash flows at irregular intervals.
    Uses the Newton-Raphson method.
    """
    if not cash_flows:
        return None

    # Sort cash flows by date and remove zero cash flows
    cash_flows = sorted([(d, c) for d, c in cash_flows if c != 0], key=lambda x: x[0])
    if not cash_flows:
        return None

    # IRR exists only if there is at least one positive and one negative cash flow
    if all(c > 0 for _, c in cash_flows) or all(c < 0 for _, c in cash_flows):
        return None

    # Special case: all cash flows on the same day.
    # Annualized IRR is undefined/infinite, so we return simple return.
    if all(d == cash_flows[0][0] for d, _ in cash_flows):
        total_in = sum(-c for _, c in cash_flows if c < 0)
        total_out = sum(c for _, c in cash_flows if c > 0)
        if total_in > 0:
            return float((total_out - total_in) / total_in)
            return 0.0

    def xnpv(rate: float, cash_flows: list[tuple[date, Decimal]]) -> float:
        d0 = cash_flows[0][0]
        return sum(
            [float(c) / (1 + rate) ** ((d - d0).days / 365.0) for d, c in cash_flows]
        )

    def xnpv_derivative(rate: float, cash_flows: list[tuple[date, Decimal]]) -> float:
        d0 = cash_flows[0][0]
        return sum(
            [
                float(c)
                * (-(d - d0).days / 365.0)
                * (1 + rate) ** (-(d - d0).days / 365.0 - 1)
                for d, c in cash_flows
            ]
        )

    # Initial guess
    try:
        total_in = sum(-c for _, c in cash_flows if c < 0)
        total_out = sum(c for _, c in cash_flows if c > 0)
        d0 = min(d for d, _ in cash_flows)
        dn = max(d for d, _ in cash_flows)
        days = (dn - d0).days
        if days > 0 and total_in > 0 and total_out > 0:
            rate = (float(total_out) / float(total_in)) ** (365.0 / days) - 1
        else:
            rate = 0.1
    except ZeroDivisionError, OverflowError, ValueError:
        rate = 0.1

    for _ in range(100):
        try:
            f_val = xnpv(rate, cash_flows)
            f_prime = xnpv_derivative(rate, cash_flows)
            if f_prime == 0:
                break
            new_rate = rate - f_val / f_prime
            if abs(new_rate - rate) < 1e-6 * max(1.0, abs(rate)):
                return new_rate
            rate = new_rate
        except OverflowError, ZeroDivisionError, TypeError, ValueError:
            return None

    return None


@log_exceptions(default=None, message="Yahoo Finance ticker initialization failed.")
def _get_ticker(symbol: str) -> yf.Ticker | None:
    return yf.Ticker(symbol)


@log_exceptions(default=None, message="Yahoo Finance history request failed.")
def _get_history(ticker: yf.Ticker, start: date, end: date):
    return ticker.history(start=start, end=end, interval="1d")


@log_exceptions(default=None, message="Yahoo Finance price lookup failed.")
def _get_price(ticker: yf.Ticker):
    price = ticker.fast_info.get("last_price")
    if price is None:
        price = ticker.info.get("regularMarketPrice")
    return price


@log_exceptions(
    default=None,
    message="Yahoo Finance price conversion failed.",
    exception_types=(InvalidOperation, TypeError, ValueError),
)
def _safe_decimal(value) -> Decimal | None:
    return Decimal(str(value))


def fetch_yahoo_finance_price(
    symbol: str,
    price_date: date | None = None,
) -> Decimal | None:
    if not symbol:
        return None

    if price_date:
        ticker = _get_ticker(symbol)
        if ticker is None:
            return None
        # Look back up to 5 days to find the latest available price
        history = _get_history(
            ticker,
            start=price_date - timedelta(days=5),
            end=price_date + timedelta(days=1),
        )
        if history is None:
            return None

        if history.empty:
            return None

        # Filter for data up to and including the price_date
        history = history[history.index.date <= price_date]  # pyright: ignore[reportAttributeAccessIssue]
        if history.empty:
            return None

        price = history["Close"].iloc[-1]  # pyright: ignore[reportAttributeAccessIssue]
        return _safe_decimal(price)

    ticker = _get_ticker(symbol)
    if ticker is None:
        return None

    price = _get_price(ticker)
    if price is None:
        return None

    return _safe_decimal(price)


def fetch_fx_rate(
    base_currency: str,
    target_currency: str,
    rate_date: date | None = None,
) -> Decimal | None:
    if not base_currency or not target_currency:
        return None
    if base_currency == target_currency:
        return Decimal("1")

    symbol = f"{base_currency}{target_currency}=X"
    if rate_date:
        ticker = _get_ticker(symbol)
        if ticker is None:
            return None
        # Look back up to 5 days to find the latest available rate
        history = _get_history(
            ticker,
            start=rate_date - timedelta(days=5),
            end=rate_date + timedelta(days=1),
        )
        if history is None:
            return None

        if history.empty:
            return None

        # Filter for data up to and including the rate_date
        history = history[history.index.date <= rate_date]  # pyright: ignore[reportAttributeAccessIssue]
        if history.empty:
            return None

        price = history["Close"].iloc[-1]  # pyright: ignore[reportAttributeAccessIssue]
        return _safe_decimal(price)

    ticker = _get_ticker(symbol)
    if ticker is None:
        return None

    price = _get_price(ticker)
    if price is None:
        return None

    return _safe_decimal(price)
