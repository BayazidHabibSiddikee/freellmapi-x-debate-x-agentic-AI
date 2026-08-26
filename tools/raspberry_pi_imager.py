#!/usr/bin/env python3
# tools/raspberry_pi_imager.py — Download the latest Raspberry Pi Imager
#
# Queries the GitHub releases for raspberrypi/rpi-imager, finds the
# correct asset for the requested platform, and downloads it with
# progress indication and size verification.
#
# Usage:
#   python3 raspberry_pi_imager.py                     # auto-detect platform
#   python3 raspberry_pi_imager.py --platform windows  # force Windows .exe
#   python3 raspberry_pi_imager.py --platform linux-amd64
#   python3 raspberry_pi_imager.py --list              # list available assets
#   python3 raspberry_pi_imager.py --output /tmp       # custom output dir
#   python3 raspberry_pi_imager.py --overwrite         # re-download even if cached
#
# Importable API:
#   from raspberry_pi_imager import download_imager
#   result = download_imager(platform_key="linux-amd64", output_dir="/tmp")

import os
import sys
import argparse
import platform as platform_mod
import requests

# ── Configuration ──────────────────────────────────────────────────────────────
GITHUB_API_URL = "https://api.github.com/repos/raspberrypi/rpi-imager/releases/latest"
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300  # large files take time
CHUNK_SIZE = 8192

# Platform key → asset-name substring that uniquely identifies the right file.
# Linux entries exclude the CLI-only packages (which have "cli" in the name).
PLATFORM_PATTERNS = {
    "windows": ".exe",
    "macos": ".dmg",
    "linux-amd64": "_amd64.deb",
    "linux-arm64": "_arm64.deb",
    "linux-armhf": "_armhf.deb",
}

# ── Platform detection ─────────────────────────────────────────────────────────

def detect_platform() -> str:
    """Auto-detect the appropriate Raspberry Pi Imager platform for this machine."""
    system = platform_mod.system().lower()
    machine = platform_mod.machine().lower()

    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-amd64"
        if machine in ("aarch64", "arm64"):
            return "linux-arm64"
        if machine in ("armv7l", "armhf"):
            return "linux-armhf"
        return "linux-amd64"  # fallback for unknown Linux arch
    # Unknown system — default to the most common Linux package
    return "linux-amd64"


# ── Release info ───────────────────────────────────────────────────────────────

def get_latest_release() -> dict:
    """Fetch the latest release metadata from the GitHub API.

    Returns the parsed JSON dict (contains tag_name, assets, …).
    Raises RuntimeError on HTTP or network errors.
    """
    try:
        resp = requests.get(
            GITHUB_API_URL, timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "raspberry-pi-imager-tool"},
        )
        data = resp.json()
        if isinstance(data, dict) and data.get("message") == "Not Found":
            raise RuntimeError(f"API error: {data['message']}")
        resp.raise_for_status()
        return data
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"GitHub API HTTP error: {e}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error contacting GitHub API: {e}") from e


def find_asset(release: dict, platform_key: str) -> dict:
    """Find the download asset for *platform_key* within *release*.

    For Linux .deb platforms, CLI-only packages (name contains "cli") are
    deprioritised so the full GUI installer is preferred.

    Raises ValueError for an unknown platform_key.
    Raises RuntimeError when no matching asset exists or the release has no assets.
    """
    if platform_key not in PLATFORM_PATTERNS:
        raise ValueError(
            f"Unknown platform '{platform_key}'. "
            f"Available: {sorted(PLATFORM_PATTERNS)}"
        )

    pattern = PLATFORM_PATTERNS[platform_key]
    assets = release.get("assets", [])
    if not assets:
        raise RuntimeError(
            f"No assets found in release {release.get('tag_name', '?')}"
        )

    matches = [a for a in assets if pattern in a["name"].lower()]
    if not matches:
        raise RuntimeError(
            f"No asset matching '{pattern}' for platform '{platform_key}'. "
            f"Available: {[a['name'] for a in assets]}"
            )

    # Prefer GUI deb over CLI deb when both match
    if pattern.endswith(".deb"):
        gui_only = [a for a in matches if "cli" not in a["name"].lower()]
        if gui_only:
            matches = gui_only

    return matches[0]


# ── Download ───────────────────────────────────────────────────────────────────

def download_asset(asset: dict, output_dir: str = None,
                   overwrite: bool = False) -> str:
    """Download a single release asset with progress indication.

    Args:
        asset:  Dict with name, size, browser_download_url (from GitHub API).
        output_dir:  Directory to save the file (default: tools/downloads/).
        overwrite:   If True, re-download even when the file already exists.

    Returns:
        The filepath of the downloaded file.

    Raises:
        RuntimeError on download failure (partial file is cleaned up).
    """
    if output_dir is None:
        output_dir = DEFAULT_DOWNLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)

    name = asset["name"]
    url = asset["browser_download_url"]
    expected_size = asset.get("size", 0)
    filepath = os.path.join(output_dir, name)

    # Skip if already downloaded with correct size
    if os.path.exists(filepath) and not overwrite:
        actual_size = os.path.getsize(filepath)
        if actual_size == expected_size:
            print(f"  [skip] Already downloaded: {filepath}"
                  f" ({actual_size / 1024 / 1024:.1f} MB)")
            return filepath
        print(f"  [resume] File exists but size mismatch "
              f"(expected {expected_size}, got {actual_size}) — re-downloading")

    print(f"  [download] {url[:80]}...")
    size_mb = expected_size / 1024 / 1024 if expected_size else 0
    print(f"  [target]  {filepath} ({size_mb:.1f} MB)")

    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True,
                            headers={"User-Agent": "raspberry-pi-imager-tool"})
        resp.raise_for_status()

        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if expected_size > 0:
                        pct = downloaded / expected_size * 100
                        sys.stdout.write(
                            f"\r  [progress] {pct:5.1f}%  "
                            f"({downloaded / 1024 / 1024:.1f} / {size_mb:.1f} MB)"
                        )
                        sys.stdout.flush()

        sys.stdout.write("\n")

        actual_size = os.path.getsize(filepath)
        if expected_size > 0 and actual_size != expected_size:
            print(f"  [warn] Size mismatch: expected {expected_size} bytes, "
                  f"got {actual_size} bytes")
        else:
            print(f"  [saved] {filepath} ({actual_size / 1024 / 1024:.1f} MB)")

        return filepath

    except Exception as e:
        # Clean up partial file so we don't leave corrupt downloads
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        raise RuntimeError(f"Download failed: {e}") from e


# ── Public API ─────────────────────────────────────────────────────────────────

def download_imager(platform_key: str = None, output_dir: str = None,
                    overwrite: bool = False) -> dict:
    """Download the latest Raspberry Pi Imager for the given platform.

    Args:
        platform_key:  One of 'auto', 'windows', 'macos', 'linux-amd64',
                       'linux-arm64', 'linux-armhf'.  If None or 'auto',
                       the platform is auto-detected from this machine.
        output_dir:    Directory to save the installer (default: tools/downloads/).
        overwrite:     Re-download even when the file already exists.

    Returns:
        Dict with keys: ok, version, platform, filepath, url, size_bytes,
                        asset_name.  Always ok=True on success.
    """
    if platform_key is None or platform_key == "auto":
        platform_key = detect_platform()

    release = get_latest_release()
    asset = find_asset(release, platform_key)
    filepath = download_asset(asset, output_dir, overwrite)

    return {
        "ok": True,
        "version": release.get("tag_name", ""),
        "platform": platform_key,
        "filepath": filepath,
        "url": asset["browser_download_url"],
        "size_bytes": asset.get("size", 0),
        "asset_name": asset["name"],
    }


def list_available_assets() -> list:
    """List all assets in the latest Raspberry Pi Imager release.

        Returns a list of asset dicts (name, size, browser_download_url).
    """
    release = get_latest_release()
    return release.get("assets", [])


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Extracted for testability."""
    parser = argparse.ArgumentParser(
        description="Download the latest Raspberry Pi Imager from GitHub releases"
    )
    parser.add_argument(
        "--platform", "-p", default="auto",
        choices=["auto"] + sorted(PLATFORM_PATTERNS.keys()),
        help="Target platform (default: auto-detect from this machine)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help=f"Output directory (default: {DEFAULT_DOWNLOAD_DIR})",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Re-download even if the file already exists",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available assets for the latest release and exit",
    )
    return parser


def main(argv: list = None) -> int:
    """CLI entrypoint. Returns the intended exit code.

    Args:
        argv:  Optional list of arguments (defaults to sys.argv[1:]).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        try:
            assets = list_available_assets()
            release = get_latest_release()
            print(f"Latest release: {release.get('tag_name', '?')} "
                  f"(published {release.get('published_at', '?')})\n")
            print(f"{'Asset':<55} {'Size':>12}")
            print("-" * 70)
            for a in assets:
                size_mb = a["size"] / 1024 / 1024
                print(f"  {a['name']:<53} {size_mb:>8.1f} MB")
        except Exception as e:
            print(f"[error] {e}")
            return 1
        return 0

    try:
        result = download_imager(
            platform_key=args.platform,
            output_dir=args.output,
            overwrite=args.overwrite,
        )
        print(f"\n✓ Done: {result['filepath']}")
        print(f"  Version:  {result['version']}")
        print(f"  Platform: {result['platform']}")
        print(f"  Size:     {result['size_bytes'] / 1024 / 1024:.1f} MB")
        print(f"  URL:      {result['url']}")
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

