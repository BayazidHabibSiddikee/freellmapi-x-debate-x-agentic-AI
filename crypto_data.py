"""Inline crypto price fetch — no GUI, returns data string for Marin."""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_crypto_price(coin: str = "bitcoin") -> str:
    coin = coin.lower().strip()
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
        data = requests.get(url, headers=HEADERS, timeout=8).json()
        if coin not in data:
            return f"[CRYPTO ERROR] '{coin}' not found on CoinGecko."
        d = data[coin]
        price  = d.get("usd", "N/A")
        change = d.get("usd_24h_change")
        mcap   = d.get("usd_market_cap")
        change_str = f"{change:+.2f}%" if change is not None else "N/A"
        mcap_str   = f"${mcap/1e9:.2f}B" if mcap else "N/A"
        return (f"{coin.title()} — Price: ${price:,.2f} USD | "
                f"24h Change: {change_str} | Market Cap: {mcap_str}")
    except Exception as e:
        return f"[CRYPTO ERROR] {e}"
