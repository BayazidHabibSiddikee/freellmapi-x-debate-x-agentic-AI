#!/usr/bin/env python3
"""
swordfish — app launcher
a minimal launcher for everyday apps
"""

import subprocess
import sys
import shutil

# ── app registry ──────────────────────────────────────────────────────────────
APPS = {
    # ── browsers ──────────────────────────────────────────────────────────────
    "swordfish":     ("Your handmade browser",          "swordfish"),
    "brave":         ("Brave browser",                  "brave"),
    "chromium":      ("Chromium browser",               "chromium"),
    "zen":           ("Zen browser",                    "zen-browser"),

    # ── terminals ─────────────────────────────────────────────────────────────
    "alacritty":     ("GPU terminal",                   "alacritty"),
    "ghostty":       ("Modern terminal",                "ghostty"),

    # ── text editors / notes ──────────────────────────────────────────────────
    "code":          ("VS Code",                        "code"),
    "obsidian":      ("Obsidian notes",                 "obsidian"),
    "geany":         ("Geany editor",                   "geany"),
    "vim":           ("Vim (in terminal)",              "alacritty -e vim"),

    # ── file manager ──────────────────────────────────────────────────────────
    "files":         ("Nautilus file manager",          "nautilus"),

    # ── media ─────────────────────────────────────────────────────────────────
    "mpv":           ("MPV media player",               "mpv"),
    "blender":       ("Blender 3D",                     "blender"),
    "feh":           ("Image viewer",                   "feh"),
    "pavucontrol":   ("Audio mixer",                    "pavucontrol"),
    "record":        ("Screen recorder",                "simplescreenrecorder"),

    # ── documents / PDFs ──────────────────────────────────────────────────────
    "okular":        ("PDF/document viewer",            "okular"),
    "zathura":       ("Minimal PDF viewer",             "zathura"),

    # ── system tools ──────────────────────────────────────────────────────────
    "btop":          ("System monitor",                 "alacritty -e btop"),
    "htop":          ("Process monitor",                "alacritty -e htop"),
    "gparted":       ("Disk partition manager",         "gparted"),
    "vpn":           ("Proton VPN",                     "proton-vpn-gtk-app"),

    # ── screenshot ────────────────────────────────────────────────────────────
    "shot":          ("Take a screenshot (maim)",       "maim ~/Pictures/screenshot_$(date +%s).png"),
}

CATEGORIES = {
    "🌐  browsers":      ["swordfish", "brave", "chromium", "zen"],
    "🖥️  terminals":     ["alacritty", "ghostty"],
    "✏️  editors/notes": ["code", "obsidian", "geany", "vim"],
    "📁  files":         ["files"],
    "🎬  media":         ["mpv", "blender", "feh", "pavucontrol", "record"],
    "📄  documents":     ["okular", "zathura"],
    "⚙️  system":        ["btop", "htop", "gparted", "vpn", "shot"],
}

# ── colours (ANSI) ────────────────────────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
DIM = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA = "\033[95m"
WHITE  = "\033[97m"

# ── helpers ───────────────────────────────────────────────────────────────────

def is_available(cmd: str) -> bool:
    """Check if the first word of a command is on PATH."""
    return shutil.which(cmd.split()[0]) is not None


def launch(cmd: str):
    """Launch a command detached from this process."""
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"{GREEN}✓ launched:{R} {cmd}")
    except Exception as e:
        print(f"{RED}✗ failed:{R} {e}")


def print_banner():
    print(f"""
{CYAN}{B}
  ███████╗██╗    ██╗ ██████╗ ██████╗ ██████╗ ███████╗██╗███████╗██╗  ██╗
  ██╔════╝██║    ██║██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║██╔════╝██║  ██║
  ███████╗██║ █╗ ██║██║   ██║██████╔╝██║  ██║█████╗  ██║███████╗███████║
  ╚════██║██║███╗██║██║   ██║██╔══██╗██║  ██║██╔══╝  ██║╚════██║██╔══██║
  ███████║╚███╔███╔╝╚██████╔╝██║  ██║██████╔╝██║     ██║███████║██║  ██║
  ╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝
{R}{DIM}  app launcher · type a name or number to launch{R}
""")


def print_apps():
    for cat, keys in CATEGORIES.items():
        print(f"  {YELLOW}{B}{cat}{R}")
        for key in keys:
            desc, cmd = APPS[key]
            avail = GREEN + "●" + R if is_available(cmd) else RED + "○" + R
            print(f"    {avail}  {CYAN}{key:<16}{R} {DIM}{desc}{R}")
        print()


def interactive():
    print_banner()
    print_apps()

    # build a flat ordered list for number selection
    ordered = []
    for keys in CATEGORIES.values():
        for k in keys:
            ordered.append(k)

    while True:
        try:
            raw = input(f"{WHITE}{B}launch ›{R} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}bye{R}")
            sys.exit(0)

        if not raw or raw in ("q", "quit", "exit"):
            print(f"{DIM}bye{R}")
            break

        if raw in ("h", "help", "?"):
            print_apps()
            continue

        # number shortcut
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(ordered):
                raw = ordered[idx]
            else:
                print(f"{RED}no app #{raw}{R}")
                continue

        if raw in APPS:
            _, cmd = APPS[raw]
            if not is_available(cmd):
                print(f"{RED}✗ '{cmd.split()[0]}' not found on PATH{R}")
            else:
                launch(cmd)
        else:
            # fuzzy-ish: show matches
            matches = [k for k in APPS if raw in k]
            if matches:
                print(f"{YELLOW}did you mean:{R} " + "  ".join(f"{CYAN}{m}{R}" for m in matches))
            else:
                print(f"{RED}unknown app '{raw}' — type 'help' to list all{R}")


def cli_launch(name: str):
    """Non-interactive: swordfish.py <appname>"""
    key = name.lower()
    if key not in APPS:
        matches = [k for k in APPS if key in k]
        if matches:
            print(f"did you mean: {', '.join(matches)}")
        else:
            print(f"unknown app '{key}'")
        sys.exit(1)
    _, cmd = APPS[key]
    if not is_available(cmd):
        print(f"'{cmd.split()[0]}' not found on PATH")
        sys.exit(1)
    launch(cmd)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_launch(sys.argv[1])
    else:
        interactive()
