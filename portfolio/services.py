from __future__ import annotations

from decimal import Decimal, InvalidOperation

import yfinance as yf


def fetch_yahoo_finance_price(symbol: str) -> Decimal | None:
    if not symbol:
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
