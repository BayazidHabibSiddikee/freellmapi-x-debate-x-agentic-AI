#!/usr/bin/env python3
# tools/news.py — runs as its own process
# Opens a news website in the default browser.
# Usage: python news.py --source BBC

import sys, argparse
import webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.tts import speak_male as talk2

SOURCES = {
    # International
    "BBC":            "https://www.bbc.com/news",
    "AlJazeera":      "https://www.aljazeera.com",
    "Reuters":        "https://www.reuters.com",
    "AP":             "https://apnews.com",
    "DW":             "https://www.dw.com/en/news",
    "France24":       "https://www.france24.com/en",
    "TheGuardian":    "https://www.theguardian.com/international",
    # South Asia
    "NDTV":           "https://www.ndtv.com",
    "TheHindu":       "https://www.thehindu.com",
    "DailyProthom":   "https://en.prothomalo.com",
    "DhakaTribune":   "https://www.dhakatribune.com",
    "DailyStarBD":    "https://www.thedailystar.net",
    # Middle East
    "ArabNews":       "https://www.arabnews.com",
    "TRTWorld":       "https://www.trtworld.com",
    # Financial
    "Bloomberg":      "https://www.bloomberg.com/news",
    "FinancialTimes": "https://www.ft.com",
    "CNBC":           "https://www.cnbc.com/world",
    # Tech
    "TechCrunch":     "https://techcrunch.com",
    "TheVerge":       "https://www.theverge.com",
}


def open_news(source: str = "BBC"):
    url = SOURCES.get(source, SOURCES["BBC"])
    print(f"\u2192 Fetching latest news from [{source}]")
    try:
        talk2(f"Opening news from {source}.")
        webbrowser.open(url)
    except Exception:
        talk2("Could not open news.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Open news website")
    parser.add_argument('--source', type=str, default="BBC",
                        choices=list(SOURCES.keys()),
                        help=f"News source: {', '.join(SOURCES.keys())}")
    args = parser.parse_args()
    open_news(args.source)
