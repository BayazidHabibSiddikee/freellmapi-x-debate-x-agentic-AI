import httpx
from bs4 import BeautifulSoup
import json
import os
import asyncio
from datetime import datetime
import ollama

# ── Configuration ─────────────────────────────────────────────────────────────
STORAGE_DIR = "storage"
NEWS_FILE   = os.path.join(STORAGE_DIR, "latest_news.json")
MODEL       = "qwen2.5:0.5b"

# Telegram Config
TELEGRAM_TOKEN   = "............."
TELEGRAM_CHAT_ID = "................"

# ── RSS Sources ────────────────────────────────────────────────────────────────
# Add or remove feeds here. Key = display name, value = RSS URL.
RSS_SOURCES = {
    # International
    "BBC":          "http://feeds.bbci.co.uk/news/world/rss.xml",
    "AlJazeera":    "https://www.aljazeera.com/xml/rss/all.xml",
    "Reuters":      "https://feeds.reuters.com/reuters/worldNews",
    "AP":           "https://rsshub.app/apnews/topics/apf-topnews",
    "DW":           "https://rss.dw.com/rdf/rss-en-world",
    "France24":     "https://www.france24.com/en/rss",
    "TheGuardian":  "https://www.theguardian.com/world/rss",
    # South Asia
    "NDTV":         "https://feeds.feedburner.com/ndtvnews-top-stories",
    "TheHindu":     "https://www.thehindu.com/news/international/?service=rss",
    "DhakaTribune": "https://www.dhakatribune.com/feed",
    "DailyStarBD":  "https://www.thedailystar.net/rss.xml",
    # Middle East
    "ArabNews":     "https://www.arabnews.com/rss.xml",
    "TRTWorld":     "https://www.trtworld.com/rss",
    # Financial
    "CNBC":         "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    # Tech
    "TechCrunch":   "https://techcrunch.com/feed/",
    "TheVerge":     "https://www.theverge.com/rss/index.xml",
}

# Set to a list of keys to restrict which feeds run, e.g. ["BBC", "Reuters"]
# Leave as None to harvest ALL sources above.
ACTIVE_SOURCES   = None
ITEMS_PER_SOURCE = 20   # headlines fetched per feed


# ── Fetching ──────────────────────────────────────────────────────────────────
async def fetch_source(client: httpx.AsyncClient, name: str, url: str) -> list:
    """Fetch and parse one RSS feed. Returns a list of news item dicts."""
    try:
        response = await client.get(url, timeout=15.0)
        response.raise_for_status()
        soup  = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item", limit=ITEMS_PER_SOURCE)
        results = []
        for item in items:
            title       = item.find("title")
            description = item.find("description")
            if title and title.get_text().strip():
                results.append({
                    "source":    name,
                    "title":     title.get_text().strip(),
                    "summary":   description.get_text().strip() if description else "No summary available",
                    "timestamp": datetime.now().isoformat(),
                })
        print(f"  ✓ {name}: {len(results)} items")
        return results
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return []


async def fetch_all_news() -> list:
    sources = {
        k: v for k, v in RSS_SOURCES.items()
        if ACTIVE_SOURCES is None or k in ACTIVE_SOURCES
    }
    print(f"[{datetime.now()}] Fetching from {len(sources)} source(s)...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks   = [fetch_source(client, name, url) for name, url in sources.items()]
        results = await asyncio.gather(*tasks)
    return [item for source_items in results for item in source_items]


# ── Analysis ──────────────────────────────────────────────────────────────────
async def analyze_impact(news_item: dict) -> str:
    prompt = f"""
Analyze the following news headline and summary for Market Impact and Sentiment.
News: {news_item['title']}
Summary: {news_item['summary']}

Format your response exactly like this:
Impact: [Low/Medium/High] - [Affected sectors, e.g., Oil, Tech, Gold]
Sentiment: [Bullish/Bearish/Neutral]
Analysis: [One sentence explanation]
"""
    try:
        response = await asyncio.to_thread(
            ollama.generate,
            model=MODEL,
            prompt=prompt,
        )
        return response["response"].strip()
    except Exception as e:
        return f"Analysis failed: {e}"


# ── Telegram ──────────────────────────────────────────────────────────────────
async def send_telegram_notification(news_items: list):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token or chat ID missing.")
        return

    print(f"[{datetime.now()}] Sending Telegram notifications...")
    message = "<b>🌍 GLOBAL INTELLIGENCE UPDATE</b>\n\n"
    for item in news_items:
        source      = item.get("source", "")
        impact_line = item["analysis"].split("\n")[0]
        message += f"[{source}] • <b>{item['title']}</b>\n{impact_line}\n\n"

    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    os.makedirs(STORAGE_DIR, exist_ok=True)

    news = await fetch_all_news()
    if not news:
        print("No news found.")
        return

    analyzed_news = []
    for item in news:
        print(f"Analyzing [{item['source']}]: {item['title']}...")
        item["analysis"] = await analyze_impact(item)
        analyzed_news.append(item)

    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(analyzed_news, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(analyzed_news)} items to {NEWS_FILE}")

    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from database import init_db, save_news
        init_db()
        save_news(analyzed_news)
        print(f"Saved {len(analyzed_news)} items to database.")
    except Exception as e:
        print(f"DB save failed: {e}")

    await send_telegram_notification(analyzed_news)


if __name__ == "__main__":
    asyncio.run(main())
