from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import yfinance as yf


def fetch_yahoo_finance_price(
    symbol: str,
    price_date: date | None = None,
) -> Decimal | None:
    if not symbol:
        return None

    if price_date:
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(
                start=price_date,
                end=price_date + timedelta(days=1),
                interval="1d",
            )
        except Exception:
            return None

        if history.empty:
            return None

        price = history["Close"].iloc[-1]
        try:
            return Decimal(str(price))
        except (InvalidOperation, TypeError):
            return None

    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get("last_price")
        if price is None:
            price = ticker.info.get("regularMarketPrice")
    except Exception:
        return None

    if price is None:
        return None

    try:
        return Decimal(str(price))
    except (InvalidOperation, TypeError):
        return None


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
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(
                start=rate_date,
                end=rate_date + timedelta(days=1),
                interval="1d",
            )
        except Exception:
            return None

        if history.empty:
            return None

        price = history["Close"].iloc[-1]
        try:
            return Decimal(str(price))
        except (InvalidOperation, TypeError):
            return None

    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get("last_price")
        if price is None:
            price = ticker.info.get("regularMarketPrice")
    except Exception:
        return None

    if price is None:
        return None

    try:
        return Decimal(str(price))
    except (InvalidOperation, TypeError):
        return None
