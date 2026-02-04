from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import yfinance as yf

from core.decorators import log_exceptions


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
