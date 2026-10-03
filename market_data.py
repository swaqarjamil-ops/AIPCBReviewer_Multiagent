"""
market_data.py
--------------
Small runtime helper for the USD -> PKR conversion used by the costing
agent. The rate is fetched from Frankfurter when possible. A Streamlit
secret/environment variable can override it with USD_PKR_RATE.
"""

import os

import requests


DEFAULT_USD_PKR_RATE = 280.0


def get_usd_pkr_rate() -> tuple[float, str]:
    """Return (USD-to-PKR rate, source label) with a safe fallback."""
    configured = os.getenv("USD_PKR_RATE", "").strip()
    if configured:
        try:
            rate = float(configured)
            if rate > 0:
                return rate, "Configured USD_PKR_RATE"
        except ValueError:
            pass

    try:
        response = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD", "to": "PKR"},
            timeout=8,
        )
        response.raise_for_status()
        rate = float(response.json()["rates"]["PKR"])
        if rate > 0:
            return rate, "Frankfurter live FX rate"
    except Exception:
        pass

    return DEFAULT_USD_PKR_RATE, "Fallback estimate"
