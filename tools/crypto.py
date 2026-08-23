#!/usr/bin/env python3
# tools/crypto.py — Live crypto price tracker, runs as its own process
# Usage: python crypto.py --coin ethereum

import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
import requests
import arrow

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def run(currency: str = "bitcoin"):
    print(f"\u2192 Fetching market price for [{currency.title()}]")
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={currency}&vs_currencies=usd")
    root = tk.Tk()
    root.title(f"{currency.title()} Watch")
    root.geometry("400x200")

    label_time  = tk.Label(root, text='', fg='Blue',  font=("Helvetica", 24))
    label_price = tk.Label(root, text='', fg='Red',   font=("Helvetica", 22))
    label_time.pack(pady=10)
    label_price.pack()

    def update():
        try:
            data = requests.get(url, headers=HEADERS, timeout=5).json()
            if currency in data:
                price = data[currency]['usd']
                label_time.configure(
                    text=f"{arrow.now().format('DD-MM-YYYY')}\n{arrow.now().format('HH:mm:ss')}"
                )
                label_price.configure(text=f"{currency.title()}: ${price:,.2f}")
            else:
                label_price.configure(text=f"'{currency}' not found")
        except Exception as e:
            label_price.configure(text=f"Error: {e}")
        root.after(1000, update)

    update()
    root.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Live crypto price tracker")
    parser.add_argument('--coin', type=str, default="bitcoin",
                        help="Coin id: bitcoin, ethereum, solana, etc.")
    parser.add_argument('--plot', type=str, help="Fallback plot argument")
    parser.add_argument('--timeframe', type=str, help="Fallback timeframe argument")
    args, unknown = parser.parse_known_args()
    
    if args.plot and not args.coin:
        coins = [c.strip() for c in args.plot.split(',')]
        # Map some common symbols if needed, or assume they are proper ids
        coin_map = {'ETH': 'ethereum', 'BTC': 'bitcoin', 'SOL': 'solana'}
        args.coin = coin_map.get(coins[0].upper(), coins[0])

    run(args.coin.lower().strip())
