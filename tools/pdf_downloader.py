import os
import re
import sys
import requests


# ── Configuration ──────────────────────────────────────────────────────────────
CAMOFOX_URL = "http://localhost:9377"
USER_ID = "pdf_downloader"
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
REQUEST_TIMEOUT = 30


# ── Search ─────────────────────────────────────────────────────────────────────

def _search_via_knowledge_hub(query: str) -> list:
    """Search using knowledge_hub.search_pdfs (Camoufox → ddgs → Google)."""
    try:
        from knowledge_hub import search_pdfs
        results = search_pdfs(query)
        out = []
        for r in results:
            href = r.get("href") or r.get("link") or r.get("url") or ""
            title = r.get("title") or r.get("body") or ""
            if href:
                out.append({"title": title.strip(), "url": href.strip()})
        return out
    except Exception as e:
        print(f"  [knowledge_hub] search failed: {e}")
        return []


def _search_via_camoufox(query: str, max_results: int = 5) -> list:
    """Direct Camoufox search with DOM extraction (standalone fallback)."""
    try:
        search_url = f"https://duckduckgo.com/?q={requests.utils.quote(query)}"
        open_res = requests.post(
            f"{CAMOFOX_URL}/tabs/open",
            json={"userId": USER_ID, "url": search_url, "timeout": 30000},
            timeout=5,
        )
        open_data = open_res.json()
        if not open_data.get("ok"):
            return []
        tab_id = open_data["tabId"]

        js = """
        Array.from(document.querySelectorAll('[data-result="web"] article')).slice(0,10).map(a => ({
            title: a.querySelector('h2')?.innerText || '',
            href:  a.querySelector('a[href]')?.href || '',
            body:  a.querySelector('[data-result="snippet"]')?.innerText || ''
        }))
        """
        eval_res = requests.post(
            f"{CAMOFOX_URL}/tabs/{tab_id}/evaluate",
            json={"userId": USER_ID, "expression": js},
            timeout=15,
        )
        eval_data = eval_res.json()
        if eval_data.get("ok") and isinstance(eval_data.get("result"), list):
            out = []
            for r in eval_data["result"]:
                href = r.get("href", "")
                title = r.get("title") or r.get("body") or ""
                if href and title:
                    out.append({"title": title.strip(), "url": href.strip()})
            return out[:max_results]
    except Exception as e:
        print(f"  [camoufox] search failed: {e}")
    return []


def _search_via_stealth_browser(query: str) -> list:
    """Fallback: use stealth_browser.stealth_search and parse markdown output."""
    try:
        from stealth_browser import stealth_search
        text = stealth_search(query)
        urls = re.findall(r'(https?://[^\s\)]+)', text)
        results = []
        for url in urls:
            url = url.rstrip("›").rstrip(".")
            if "duckduckgo.com" in url:
                continue
            results.append({"title": "", "url": url})
        return results[:5]
    except Exception as e:
        print(f"  [stealth_browser] search failed: {e}")
        return []


def search_pdfs(query: str) -> list:
    """Search for PDF books. Cascade: knowledge_hub → camoufox direct → stealth_browser."""
    pdf_query = f"{query} filetype:pdf"
    print(f"[*] Searching: {pdf_query}")

    print("  Trying knowledge_hub...")
    results = _search_via_knowledge_hub(pdf_query)
    if results:
        return results

    print("  Trying Camoufox directly...")
    results = _search_via_camoufox(pdf_query)
    if results:
        return results

    print("  Trying stealth_browser fallback...")
    results = _search_via_stealth_browser(pdf_query)
    return results


# ── PDF Validation ─────────────────────────────────────────────────────────────

def validate_pdf(data: bytes) -> bool:
    """Check if downloaded data is a valid PDF (magic bytes)."""
    if len(data) < 5:
        return False
    return data[:5] == b"%PDF-"


# ── Download ───────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = name.strip('._')
    return name[:200] if name else "untitled"


def download_pdf(url: str, book_name: str, output_dir: str = None) -> str:
    """
    Download a PDF from url, save as book_name.pdf.
    Returns the saved file path, or empty string on failure.
    """
    if output_dir is None:
        output_dir = DEFAULT_DOWNLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)

    filename = _sanitize_filename(book_name) + ".pdf"
    filepath = os.path.join(output_dir, filename)

    # Skip if already downloaded
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"  [skip] Already exists: {filepath}")
        return filepath

    try:
        print(f"  [download] {url[:80]}...")
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        data = resp.content

        # Validate PDF
        if not validate_pdf(data):
            # Check if server returned HTML error page
            if b"<html" in data[:500].lower():
                print(f"  [reject] Got HTML instead of PDF from {url[:60]}")
                return ""
            # Some servers don't set correct content-type but data is valid PDF
            print(f"  [warn] PDF validation failed (content-type: {content_type})")
            return ""

        with open(filepath, "wb") as f:
            f.write(data)

        size_kb = len(data) / 1024
        print(f"  [saved] {filepath} ({size_kb:.1f} KB)")
        return filepath

    except Exception as e:
        print(f"  [error] Download failed: {e}")
        return ""


def download_books(queries: list, output_dir: str = None) -> dict:
    """
    Search and download PDFs for each query.
    Returns dict mapping query → saved filepath (or empty string on failure).
    """
    if output_dir is None:
        output_dir = DEFAULT_DOWNLOAD_DIR

    results = {}
    for query in queries:
        print(f"\n{'='*60}")
        print(f"[book] {query}")
        print(f"{'='*60}")

        search_results = search_pdfs(query)
        if not search_results:
            print(f"  [!] No results found for '{query}'")
            results[query] = ""
            continue

        # Try each result until a valid PDF is downloaded
        downloaded = False
        for i, r in enumerate(search_results[:5], 1):
            print(f"  Result {i}: {r['title'][:60] or r['url'][:60]}")
            path = download_pdf(r["url"], query, output_dir)
            if path:
                results[query] = path
                downloaded = True
                break

        if not downloaded:
            print(f"  [!] Failed to download valid PDF for '{query}'")
            results[query] = ""

    return results


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download PDF books via stealth browser search")
    parser.add_argument("books", nargs="*", help="Book names to search and download")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: downloads/)")
    args = parser.parse_args()

    if not args.books:
        parser.print_help()
        sys.exit(1)

    results = download_books(args.books, args.output)

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    for query, path in results.items():
        status = f"✓ {path}" if path else "✗ failed"
        print(f"  {query}: {status}")
