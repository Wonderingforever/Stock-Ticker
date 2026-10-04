import json
import os
import time
from datetime import datetime, timezone

import requests
import pandas as pd
import yfinance as yf


FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "").strip()

SECTIONS = {
    "leveraged": [
        ("TQQQ", "TQQQ"),
        ("SOXL", "SOXL"),
        ("NAIL", "NAIL"),
        ("FNGU", "FNGU"),
        ("NVDL", "NVDL"),
        ("FAS", "FAS"),
        ("YINN", "YINN"),
        ("YANG", "YANG"),
        ("WANT", "WANT"),
        ("RETL", "RETL"),
        ("TSLL", "TSLL"),
        ("AMDL", "AMDL"),
    ],
    "us-market": [
        ("SPY", "SPY"),
        ("QQQ", "QQQ"),
        ("ITA", "ITA"),
        ("XLI", "XLI"),
        ("VTI", "VTI"),
        ("VONG", "VONG"),
    ],
    "world-market": [
        ("EWJ", "EWJ"),
        ("MCHI", "MCHI"),
        ("EWH", "EWH"),
        ("EWU", "EWU"),
        ("EWG", "EWG"),
        ("VGK", "VGK"),
    ],
    "financials": [
        ("BLK", "BLK"),
        ("BX", "BX"),
        ("BNY", "BK"),   # BNY Mellon trades as BK
        ("KKR", "KKR"),
        ("APO", "APO"),
        ("STT", "STT"),
        ("TROW", "TROW"),
        ("BEN", "BEN"),
        ("SCHW", "SCHW"),
        ("TFC", "TFC"),
        ("JPM", "JPM"),
        ("WT", "WT"),
        ("IVZ", "IVZ"),
    ],
    "stocks": [
        ("AMZN", "AMZN"),
        ("MU", "MU"),
        ("SPCX", "SPCX"),
        ("NVDA", "NVDA"),
        ("PSA", "PSA"),
        ("TSLA", "TSLA"),
        ("PYPL", "PYPL"),
        ("COIN", "COIN"),
        ("BRK.B", "BRK-B"),
        ("META", "META"),
        ("AVGO", "AVGO"),
        ("MSFT", "MSFT"),
        ("GOOGL", "GOOGL"),
        ("AAPL", "AAPL"),
    ],
    "precious": [
        ("Silver", "SLV"),
        ("Gold", "GLD"),
        ("CPER", "CPER"),
    ],
}


def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return round(float(value), 4)
    except Exception:
        return None


def pct_change(current, old):
    try:
        if current is None or old is None or float(old) == 0:
            return None
        return ((float(current) / float(old)) - 1.0) * 100.0
    except Exception:
        return None


def close_on_or_before(close_series, target_timestamp):
    eligible = close_series.loc[close_series.index <= target_timestamp]
    if eligible.empty:
        return None
    return safe_float(eligible.iloc[-1])


def finnhub_day(symbol):
    if not FINNHUB_KEY:
        return None

    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": FINNHUB_KEY}

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        if data.get("dp") is not None:
            return safe_float(data["dp"])

        c = safe_float(data.get("c"))
        pc = safe_float(data.get("pc"))
        return safe_float(pct_change(c, pc))
    except Exception as exc:
        print(f"Finnhub day failed for {symbol}: {exc}")
        return None


def historical_metrics(yf_symbol):
    try:
        hist = yf.download(
            yf_symbol,
            period="14mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if hist is None or hist.empty:
            raise RuntimeError("No Yahoo history returned")

        close = hist["Close"]

        # yfinance can return a single-column DataFrame instead of Series.
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = close.dropna()

        if close.empty:
            raise RuntimeError("No closing prices returned")

        idx = pd.DatetimeIndex(close.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
            close.index = idx

        now = pd.Timestamp.now().normalize()
        current = safe_float(close.iloc[-1])

        five_day_price = close_on_or_before(close, now - pd.Timedelta(days=5))
        one_month_price = close_on_or_before(close, now - pd.DateOffset(months=1))
        six_month_price = close_on_or_before(close, now - pd.DateOffset(months=6))
        one_year_price = close_on_or_before(close, now - pd.DateOffset(years=1))

        previous_year_end = pd.Timestamp(year=now.year - 1, month=12, day=31)
        year_end_price = close_on_or_before(close, previous_year_end)

        # Fallback daily change from historical data if Finnhub is unavailable.
        fallback_day = None
        if len(close) >= 2:
            fallback_day = pct_change(
                safe_float(close.iloc[-1]),
                safe_float(close.iloc[-2]),
            )

        return {
            "fallback_day": safe_float(fallback_day),
            "five_day": safe_float(pct_change(current, five_day_price)),
            "one_month": safe_float(pct_change(current, one_month_price)),
            "six_month": safe_float(pct_change(current, six_month_price)),
            "ytd": safe_float(pct_change(current, year_end_price)),
            "one_year": safe_float(pct_change(current, one_year_price)),
        }

    except Exception as exc:
        print(f"Historical data failed for {yf_symbol}: {exc}")
        return {
            "fallback_day": None,
            "five_day": None,
            "one_month": None,
            "six_month": None,
            "ytd": None,
            "one_year": None,
        }


def main():
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {},
    }

    for section_id, symbols in SECTIONS.items():
        section_rows = []

        for display_ticker, yf_symbol in symbols:
            print(f"Updating {display_ticker} ({yf_symbol})")

            metrics = historical_metrics(yf_symbol)

            # Finnhub expects US ticker convention for most of these.
            finnhub_symbol = yf_symbol.replace("-", ".") if yf_symbol == "BRK-B" else yf_symbol
            day = finnhub_day(finnhub_symbol)

            if day is None:
                day = metrics["fallback_day"]

            section_rows.append({
                "ticker": display_ticker,
                "day": safe_float(day),
                "five_day": metrics["five_day"],
                "one_month": metrics["one_month"],
                "six_month": metrics["six_month"],
                "ytd": metrics["ytd"],
                "one_year": metrics["one_year"],
            })

            # Be polite to upstream data providers.
            time.sleep(0.25)

        output["sections"][section_id] = section_rows

    os.makedirs("data", exist_ok=True)

    with open("data/market-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("Wrote data/market-data.json")


if __name__ == "__main__":
    main()
