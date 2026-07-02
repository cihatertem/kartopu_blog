from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import pandas as pd
import requests
import yfinance as yf
from yfinance import exceptions as yf_exceptions

from core.decorators import log_exceptions

logger = logging.getLogger(__name__)

YF_API_TIMEOUT = 10


def calculate_xirr(cash_flows: list[tuple[date, Decimal]]) -> float | None:
    """
    Calculates the Internal Rate of Return for a series of cash flows at irregular intervals.
    Uses the Newton-Raphson method.
    """
    if not cash_flows:
        return None

    for _, amount in cash_flows:
        if amount.is_nan() or amount.is_infinite():
            return None

    # Sort cash flows by date and remove zero cash flows
    # Single pass to filter zeros and check for positive/negative signs
    filtered_flows = []
    has_pos = False
    has_neg = False
    for flow in cash_flows:
        c = flow[1]
        if c:  # Since c is Decimal, c != 0 is equivalent to truthy check
            filtered_flows.append(flow)
            if not has_pos and c > 0:
                has_pos = True
            elif not has_neg and c < 0:
                has_neg = True

    if not filtered_flows:
        return None

    # IRR exists only if there is at least one positive and one negative cash flow
    if not (has_pos and has_neg):
        return None

    cash_flows = sorted(filtered_flows, key=lambda x: x[0])

    # Special case: all cash flows on the same day.
    # Annualized IRR is undefined/infinite, so we return simple return.
    if cash_flows[0][0] == cash_flows[-1][0]:
        total_in = sum(-c for _, c in cash_flows if c < 0)
        total_out = sum(c for _, c in cash_flows if c > 0)
        if total_in > 0:
            return float((total_out - total_in) / total_in)
        return 0.0

    return _calculate_math_xirr(cash_flows)


def _calculate_math_xirr(cash_flows: list[tuple[date, Decimal]]) -> float | None:
    def xnpv(rate: float, cash_flows: list[tuple[date, Decimal]]) -> float:
        d0 = cash_flows[0][0]
        return sum(
            float(c) / (1 + rate) ** ((d - d0).days / 365.0) for d, c in cash_flows
        )

    def xnpv_derivative(rate: float, cash_flows: list[tuple[date, Decimal]]) -> float:
        d0 = cash_flows[0][0]
        return sum(
            float(c)
            * (-(d - d0).days / 365.0)
            * (1 + rate) ** (-(d - d0).days / 365.0 - 1)
            for d, c in cash_flows
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
    except (
        ZeroDivisionError,
        OverflowError,
        ValueError,
    ):
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
        except (
            OverflowError,
            ZeroDivisionError,
            TypeError,
            ValueError,
        ):
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


def _download_yf_bulk_data(
    symbols: list[str], start: date, end: date, error_message: str
):
    try:
        return yf.download(
            symbols,
            start=start,
            end=end,
            progress=False,
            interval="1d",
            timeout=YF_API_TIMEOUT,
        )
    except (
        requests.RequestException,
        ValueError,
        yf_exceptions.YFException,
    ):
        logger.exception(f"{error_message}: %s", symbols)
        return None


@log_exceptions(default=dict, message="Yahoo Finance bulk price request failed.")  # pyright: ignore[reportArgumentType]
def fetch_yahoo_finance_prices_bulk(
    symbols: list[str],
    price_date: date | None = None,
) -> dict[str, Decimal]:
    if not symbols:
        return {}

    valid_symbols = list(dict.fromkeys(s for s in symbols if s))
    if not valid_symbols:
        return {}

    if price_date:
        start = price_date - timedelta(days=5)
        end = price_date + timedelta(days=1)
    else:
        start = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

    data = _download_yf_bulk_data(
        valid_symbols, start, end, "Yahoo Finance bulk download failed for symbols"
    )
    if data is None:
        return {}

    results: dict[str, Decimal] = {}

    if data is None or data.empty or "Close" not in data:
        return results

    close_data = data["Close"]

    if price_date:
        close_data = close_data[close_data.index.date <= price_date]  # pyright: ignore[reportAttributeAccessIssue]
        if close_data.empty:  # pyright: ignore[reportAttributeAccessIssue]
            return results

    if hasattr(close_data, "columns"):
        last_prices = close_data.ffill().iloc[-1] if not close_data.empty else None
        symbols_count = len(valid_symbols)
        for symbol in valid_symbols:
            try:
                price = None
                if last_prices is not None:
                    if symbol in close_data.columns:
                        price = last_prices[symbol]
                    elif symbols_count == 1:
                        price = last_prices.iloc[0]

                if price is not None and pd.notna(price):
                    decimal_price = _safe_decimal(price)
                    if decimal_price is not None:
                        results[symbol] = decimal_price
            except Exception:
                logger.exception("Failed to parse price for %s", symbol)
    else:
        series = close_data.dropna()
        if not series.empty:
            try:
                decimal_price = _safe_decimal(series.iloc[-1])
                if decimal_price is not None:
                    for symbol in valid_symbols:
                        results[symbol] = decimal_price
            except Exception:
                for symbol in valid_symbols:
                    logger.exception("Failed to parse price for %s", symbol)

    return results


def _parse_multiple_fx_results(
    close_data,
    pairs_by_date: dict[date | None, set[tuple[str, str]]],
    symbols_count: int,
) -> dict[tuple[str, str, date | None], Decimal]:
    results: dict[tuple[str, str, date | None], Decimal] = {}
    for d, pairs in pairs_by_date.items():
        if d is not None:
            current_close_data = close_data[close_data.index.date <= d]  # pyright: ignore[reportAttributeAccessIssue]
        else:
            current_close_data = close_data

        if current_close_data.empty:  # pyright: ignore[reportAttributeAccessIssue]
            continue

        last_prices = None
        series = None
        is_dataframe = hasattr(current_close_data, "columns")

        if is_dataframe:
            last_prices = (
                current_close_data.ffill().iloc[-1]
                if not current_close_data.empty
                else None
            )
        else:
            series = current_close_data.dropna()

        for base, target in pairs:
            if base == target:
                results[(base, target, d)] = Decimal("1")
                continue

            symbol = f"{base}{target}=X"
            try:
                price = None
                if is_dataframe and last_prices is not None:
                    if symbol in current_close_data.columns:
                        price = last_prices[symbol]
                    elif symbols_count == 1:
                        price = last_prices.iloc[0]
                elif not is_dataframe and series is not None and not series.empty:
                    price = series.iloc[-1]

                if price is not None and pd.notna(price):
                    decimal_price = _safe_decimal(price)
                    if decimal_price is not None:
                        results[(base, target, d)] = decimal_price
            except Exception:
                logger.exception("Failed to parse FX rate for %s on %s", symbol, d)

    # Ensure identical pairs are populated even if not in symbols
    for d, pairs in pairs_by_date.items():
        for p in pairs:
            if p[0] == p[1]:
                results[(p[0], p[1], d)] = Decimal("1")

    return results


@log_exceptions(
    default=dict, message="Yahoo Finance multiple bulk history request failed."
)  # pyright: ignore[reportArgumentType]
def fetch_multiple_fx_rates_bulk(
    pairs_by_date: dict[date | None, set[tuple[str, str]]],
) -> dict[tuple[str, str, date | None], Decimal]:
    """
    Fetches FX rates for multiple dates and currency pairs in a single yfinance request.
    Returns a dictionary mapping (base_currency, target_currency, rate_date) to the exchange rate.
    """
    if not pairs_by_date:
        return {}

    all_pairs = set()
    valid_dates = []

    for d, pairs in pairs_by_date.items():
        all_pairs.update(pairs)
        if d is not None:
            valid_dates.append(d)

    pairs_to_fetch = [p for p in all_pairs if p[0] != p[1]]
    if not pairs_to_fetch:
        results = {}
        for d, pairs in pairs_by_date.items():
            for p in pairs:
                results[(p[0], p[1], d)] = Decimal("1")
        return results

    symbols_map = {
        f"{base}{target}=X": (base, target) for base, target in pairs_to_fetch
    }
    symbols = list(symbols_map.keys())

    if valid_dates:
        min_date = min(valid_dates)
        max_date = max(valid_dates)
        start = min_date - timedelta(days=5)
        end = max_date + timedelta(days=1)
    else:
        start = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

    data = _download_yf_bulk_data(
        symbols, start, end, "Yahoo Finance multiple bulk download failed for symbols"
    )

    if data is None or data.empty or "Close" not in data:
        return {}

    return _parse_multiple_fx_results(data["Close"], pairs_by_date, len(symbols))


@log_exceptions(default=dict, message="Yahoo Finance bulk history request failed.")  # pyright: ignore[reportArgumentType]
def fetch_fx_rates_bulk(
    currency_pairs: list[tuple[str, str]],
    rate_date: date | None = None,
) -> dict[tuple[str, str], Decimal]:
    if not currency_pairs:
        return {}

    # Filter out identical pairs
    pairs_to_fetch = list(
        dict.fromkeys(pair for pair in currency_pairs if pair[0] != pair[1])
    )
    if not pairs_to_fetch:
        return {pair: Decimal("1") for pair in currency_pairs if pair[0] == pair[1]}

    symbols_map = {
        f"{base}{target}=X": (base, target) for base, target in pairs_to_fetch
    }
    symbols = list(symbols_map.keys())

    if rate_date:
        start = rate_date - timedelta(days=5)
        end = rate_date + timedelta(days=1)
    else:
        # Use recent period if no date specified
        start = date.today() - timedelta(days=5)
        end = date.today() + timedelta(days=1)

    # yf.download can be noisy; setting progress=False avoids stdout spam
    data = _download_yf_bulk_data(
        symbols, start, end, "Yahoo Finance bulk download failed for symbols"
    )
    if data is None:
        return {}

    if data is None or data.empty:
        return {}

    # Filter for data up to and including the rate_date
    if rate_date:
        data = data[data.index.date <= rate_date]  # pyright: ignore[reportAttributeAccessIssue]
        if data.empty:
            return {}

    results: dict[tuple[str, str], Decimal] = {}

    # If "Close" is not present, parsing fails
    if "Close" not in data:
        return {}

    close_data = data["Close"]

    if hasattr(close_data, "columns"):
        last_prices = close_data.ffill().iloc[-1] if not close_data.empty else None
        symbols_count = len(symbols)
        for symbol in symbols:
            try:
                price = None
                if last_prices is not None:
                    if symbol in close_data.columns:
                        price = last_prices[symbol]
                    elif symbols_count == 1:
                        price = last_prices.iloc[0]

                if price is not None and pd.notna(price):
                    decimal_price = _safe_decimal(price)
                    if decimal_price is not None:
                        results[symbols_map[symbol]] = decimal_price
            except Exception:
                logger.exception("Failed to parse FX rate for %s", symbol)
    else:
        series = close_data.dropna()
        if not series.empty:
            try:
                decimal_price = _safe_decimal(series.iloc[-1])
                if decimal_price is not None:
                    for symbol in symbols:
                        results[symbols_map[symbol]] = decimal_price
            except Exception:
                for symbol in symbols:
                    logger.exception("Failed to parse FX rate for %s", symbol)

    # Include identical pairs in the result
    for pair in currency_pairs:
        if pair[0] == pair[1]:
            results[pair] = Decimal("1")

    return results


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
