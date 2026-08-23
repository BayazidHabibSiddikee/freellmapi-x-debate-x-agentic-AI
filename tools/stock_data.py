"""Inline stock price fetch — no GUI, returns data string for Marin."""
import requests
import yfinance as yf

HEADERS = {"User-Agent": "Mozilla/5.0"}

def _resolve_ticker(company: str) -> str | None:
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={company}"
        res = requests.get(url, headers=HEADERS, timeout=8).json()
        quotes = res.get("quotes", [])
        return quotes[0]["symbol"] if quotes else None
    except Exception:
        return None

def fetch_stock_price(company: str) -> str:
    company = company.strip()
    ticker = company.upper() if len(company) <= 5 and company.isupper() else _resolve_ticker(company)
    if not ticker:
        return f"[STOCK ERROR] Could not find ticker for '{company}'."
    try:
        obj  = yf.Ticker(ticker)
        info = obj.info
        price  = info.get("regularMarketPrice") or info.get("currentPrice")
        name   = info.get("longName", ticker)
        change = info.get("regularMarketChangePercent")
        high   = info.get("regularMarketDayHigh")
        low    = info.get("regularMarketDayLow")
        if price is None:
            return f"[STOCK ERROR] No price data for {ticker}."
        change_str = f"{change:+.2f}%" if change is not None else "N/A"
        high_str   = f"${high:.2f}" if high else "N/A"
        low_str    = f"${low:.2f}"  if low  else "N/A"
        return (f"{name} ({ticker}) — Price: ${price:.2f} USD | "
                f"Change: {change_str} | Day High: {high_str} | Day Low: {low_str}")
    except Exception as e:
        return f"[STOCK ERROR] {e}"
