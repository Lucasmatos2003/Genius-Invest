from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import os
import pandas as pd
import yfinance as yf

# Simple in-memory cache for finance data (symbol -> (timestamp, value))
_CACHE: dict[str, tuple[float, dict]] = {}

# TTL configurable via environment (FINANCE_CACHE_TTL). Default 300s
try:
    _FINANCE_CACHE_TTL = int(os.getenv("FINANCE_CACHE_TTL", "300"))
except Exception:
    _FINANCE_CACHE_TTL = 300


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".SA", "")


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_json(url: str, timeout: int = 15) -> dict[str, Any] | None:
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except (URLError, ValueError, TimeoutError):
        return None


def get_stock_price(symbol: str) -> float | None:
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    return _safe_float(price)


def get_dividends(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    dividends = ticker.dividends
    if dividends.empty:
        return 0.0
    return float(dividends.tail(1).iloc[0])


def get_historical_prices(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=period, interval=interval)
    if history.empty:
        return pd.DataFrame()

    history = history.reset_index()
    if "Date" in history.columns:
        history["Date"] = pd.to_datetime(history["Date"]).dt.strftime("%Y-%m-%d")
    return history


def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def calculate_volatility(series: pd.Series, window: int = 20) -> pd.Series:
    returns = series.pct_change().fillna(0)
    return returns.rolling(window=window, min_periods=1).std() * 100


def get_stock_technical_analysis(symbol: str, period: str = "6mo") -> dict:
    history = get_historical_prices(symbol, period=period, interval="1d")
    if history.empty or "Close" not in history.columns:
        return {
            "sma_10": None,
            "sma_30": None,
            "rsi_14": None,
            "volatility_20d": None,
            "trend": "indisponível",
        }

    close = pd.to_numeric(history["Close"], errors="coerce")
    sma_10 = calculate_sma(close, 10).iloc[-1]
    sma_30 = calculate_sma(close, 30).iloc[-1]
    rsi_14 = float(calculate_rsi(close, 14).iloc[-1])
    vol_20d = float(calculate_volatility(close, 20).iloc[-1])

    current_price = float(close.iloc[-1])
    if current_price > sma_10 and current_price > sma_30:
        trend = "alta"
    elif current_price < sma_10 and current_price < sma_30:
        trend = "queda"
    else:
        trend = "lateral"

    return {
        "sma_10": round(float(sma_10), 2) if pd.notna(sma_10) else None,
        "sma_30": round(float(sma_30), 2) if pd.notna(sma_30) else None,
        "rsi_14": round(rsi_14, 2),
        "volatility_20d": round(vol_20d, 4),
        "trend": trend,
    }


def get_brapi_quote(symbol: str) -> dict[str, Any]:
    normalized = _normalize_symbol(symbol)
    url = f"https://brapi.dev/api/quote/{normalized}?range=1y&interval=1d"
    payload = _fetch_json(url) or {}
    result = (payload.get("results") or [{}])[0]
    if not result:
        return {}

    return {
        "symbol": result.get("symbol") or normalized,
        "shortName": result.get("shortName") or result.get("longName") or normalized,
        "price": _safe_float(result.get("regularMarketPrice") or result.get("last") or result.get("price")),
        "currency": result.get("currency") or "BRL",
        "dividend_yield": _safe_float(result.get("dividendYield") or result.get("dividendYieldAnnual")),
        "market_cap": _safe_float(result.get("marketCap") or result.get("mktCap")),
        "pe_ratio": _safe_float(result.get("trailingPE") or result.get("peRatio") or result.get("PE")),
        "roe": _safe_float(result.get("returnOnEquity") or result.get("roe")),
        "net_margin": _safe_float(result.get("netMargin") or result.get("netProfitMargin")),
        "beta": _safe_float(result.get("beta")),
        "regularMarketChangePercent": _safe_float(result.get("regularMarketChangePercent") or result.get("changePercent")),
    }


def get_symbol_news(symbol: str, limit: int = 8) -> list[dict]:
    ticker = yf.Ticker(symbol)
    news = ticker.news or []
    items: list[dict] = []

    for item in news[:limit]:
        title = item.get("title") or "Sem título"
        publisher = item.get("publisher") or "Yahoo Finance"
        link = item.get("link") or ""
        items.append({
            "title": title,
            "publisher": publisher,
            "link": link,
            "summary": item.get("summary") or title,
        })

    return items


def _get_stock_summary_core(symbol: str) -> dict:
    quote = get_brapi_quote(symbol) if symbol.upper().endswith(".SA") or symbol.upper().endswith("SA") else {}
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    history = get_historical_prices(symbol, period="6mo", interval="1d")
    technicals = get_stock_technical_analysis(symbol, period="6mo")
    price = quote.get("price") if quote.get("price") is not None else (info.get("regularMarketPrice") or info.get("currentPrice"))

    summary = {
        "symbol": symbol.upper(),
        "price": _safe_float(price),
        "currency": quote.get("currency") or info.get("currency", "BRL"),
        "market_name": quote.get("shortName") or info.get("shortName", symbol.upper()),
        "dividend_yield": quote.get("dividend_yield") if quote.get("dividend_yield") is not None else info.get("dividendYield"),
        "market_cap": quote.get("market_cap") if quote.get("market_cap") is not None else info.get("marketCap"),
        "pe_ratio": quote.get("pe_ratio") if quote.get("pe_ratio") is not None else info.get("trailingPE"),
        "roe": quote.get("roe") if quote.get("roe") is not None else info.get("returnOnEquity"),
        "net_margin": quote.get("net_margin") if quote.get("net_margin") is not None else info.get("profitMargins"),
        "beta": quote.get("beta") if quote.get("beta") is not None else info.get("beta"),
        "regularMarketChangePercent": quote.get("regularMarketChangePercent") if quote.get("regularMarketChangePercent") is not None else info.get("regularMarketChangePercent"),
        "history": history.tail(100).to_dict("records"),
        "technicals": technicals,
        "news": get_symbol_news(symbol, limit=8),
    }

    return summary


def get_stock_summary(symbol: str) -> dict:
    """Get stock summary with a simple in-memory TTL cache per symbol."""
    key = symbol.upper()
    now = time.time()
    cached = _CACHE.get(key)
    if cached:
        ts, value = cached
        if now - ts < _FINANCE_CACHE_TTL:
            return value

    # not cached or expired
    value = _get_stock_summary_core(symbol)
    try:
        _CACHE[key] = (now, value)
    except Exception:
        # never fail the function due to caching issues
        pass
    return value
