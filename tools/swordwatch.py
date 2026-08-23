#!/usr/bin/env python3
"""
swordwatch — process monitor + process killer
tracks runtime, memory, cpu, internals · and stops what you want
"""

import os
import sys
import time
import signal
import subprocess
from datetime import datetime, timedelta

try:
    import psutil
except ImportError:
    print("\033[93minstalling psutil...\033[0m")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "--quiet"])
    import psutil

# ── swordfish app list ────────────────────────────────────────────────────────
KNOWN_APPS = {
    "swordfish", "brave", "chromium", "zen-browser",
    "alacritty", "ghostty", "xterm",
    "code", "obsidian", "geany", "vim", "nano",
    "nautilus", "blender", "mpv", "feh", "pavucontrol",
    "simplescreenrecorder", "okular", "zathura",
    "btop", "htop", "gparted", "proton-vpn-gtk-app",
    "virt-manager", "docker", "podman", "rofi", "picom",
    "dunst", "variety", "piper",
}

# ── ANSI ──────────────────────────────────────────────────────────────────────
R       = "\033[0m"
B       = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"
BLUE    = "\033[94m"
BG_RED  = "\033[41m"
BG_YEL  = "\033[43m"

CLR = "\033[2J\033[H"

# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def fmt_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds, 3600)
    m, s   = divmod(rem, 60)
    days   = td.days
    if days:
        return f"{days}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"

def cpu_bar(pct: float, width: int = 12) -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if pct < 40 else YELLOW if pct < 75 else RED
    return f"{color}{bar}{R} {pct:5.1f}%"

def mem_bar(pct: float, width: int = 12) -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if pct < 40 else YELLOW if pct < 75 else RED
    return f"{color}{bar}{R} {pct:5.1f}%"

def get_open_files(proc) -> list:
    try:
        return [f.path for f in proc.open_files()]
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return []

def get_connections(proc) -> list:
    try:
        conns = proc.net_connections()
        out = []
        for c in conns:
            laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "—"
            raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "—"
            out.append(f"{c.status:<12} {laddr} → {raddr}")
        return out
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return []

def get_threads(proc) -> int:
    try:
        return proc.num_threads()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return 0

def get_cmdline(proc) -> str:
    try:
        return " ".join(proc.cmdline()) or proc.name()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return proc.name()

def get_children(proc) -> list:
    try:
        return proc.children(recursive=False)
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return []

def collect_processes(filter_known: bool = False) -> list:
    now = time.time()
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'status', 'create_time']):
        try:
            info = p.info
            name = info['name'] or ""
            if filter_known and name not in KNOWN_APPS:
                continue
            with p.oneshot():
                cpu   = p.cpu_percent(interval=None)
                mem   = p.memory_info()
                rss   = mem.rss
                vms   = mem.vms
                mem_p = p.memory_percent()
                up    = now - info['create_time']
                stat  = info['status']
                thr   = get_threads(p)
            procs.append({
                "pid":   info['pid'],
                "name":  name,
                "cpu":   cpu,
                "rss":   rss,
                "vms":   vms,
                "mem_p": mem_p,
                "up":    up,
                "stat":  stat,
                "thr":   thr,
                "proc":  p,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return procs

def find_procs(target: str) -> list:
    """Return all processes matching a name substring or exact PID."""
    results = []
    if target.isdigit():
        try:
            p = psutil.Process(int(target))
            results.append(p)
        except psutil.NoSuchProcess:
            pass
    else:
        for p in psutil.process_iter(['name', 'pid']):
            try:
                if target.lower() in p.info['name'].lower():
                    results.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return results

# ── banner ────────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""{CYAN}{B}
  ███████╗██╗    ██╗ ██████╗ ██████╗ ██████╗ ██╗    ██╗ █████╗ ████████╗ ██████╗██╗  ██╗
  ██╔════╝██║    ██║██╔═══██╗██╔══██╗██╔══██╗██║    ██║██╔══██╗╚══██╔══╝██╔════╝██║  ██║
  ███████╗██║ █╗ ██║██║   ██║██████╔╝██║  ██║██║ █╗ ██║███████║   ██║   ██║     ███████║
  ╚════██║██║███╗██║██║   ██║██╔══██╗██║  ██║██║███╗██║██╔══██║   ██║   ██║     ██╔══██║
  ███████║╚███╔███╔╝╚██████╔╝██║  ██║██████╔╝╚███╔███╔╝██║  ██║   ██║   ╚██████╗██║  ██║
  ╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝  ╚═╝    ╚═════╝╚═╝  ╚═╝
{R}{DIM}  process monitor + process killer  ·  Ctrl+C exits any view{R}
""")

# ── kill engine ───────────────────────────────────────────────────────────────

SIGNAL_MAP = {
    "1":  ("SIGHUP",  signal.SIGHUP,  "hangup — reload config"),
    "2":  ("SIGINT",  signal.SIGINT,  "interrupt — like Ctrl+C"),
    "3":  ("SIGQUIT", signal.SIGQUIT, "quit + core dump"),
    "9":  ("SIGKILL", signal.SIGKILL, "force kill — instant, no cleanup"),
    "15": ("SIGTERM", signal.SIGTERM, "graceful terminate (default)"),
    "18": ("SIGCONT", signal.SIGCONT, "resume a paused process"),
    "19": ("SIGSTOP", signal.SIGSTOP, "pause / freeze process"),
}

def _send_signal(proc: psutil.Process, sig: int, sig_name: str, include_children: bool) -> dict:
    """Send a signal to proc (and optionally its children). Returns result dict."""
    results = {"ok": [], "fail": []}

    targets = []
    if include_children:
        try:
            targets = proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    targets.append(proc)

    for t in targets:
        try:
            name = t.name()
            pid  = t.pid
            t.send_signal(sig)
            results["ok"].append((pid, name))
        except psutil.NoSuchProcess:
            results["fail"].append((t.pid, "already gone"))
        except psutil.AccessDenied:
            results["fail"].append((t.pid, "access denied — try sudo"))
        except Exception as e:
            results["fail"].append((t.pid, str(e)))

    return results


def _confirm(prompt: str) -> bool:
    try:
        ans = input(f"  {YELLOW}{prompt}{R} [y/N] ").strip().lower()
        return ans == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def _pick_signal() -> tuple:
    """Let user pick a signal. Returns (sig_int, sig_name) or (None, None)."""
    print(f"\n  {B}choose signal:{R}")
    for k, (name, _, desc) in SIGNAL_MAP.items():
        marker = f"{GREEN}← recommended{R}" if k == "15" else ""
        print(f"    {CYAN}[{k:>2}]{R}  {B}{name:<10}{R}  {DIM}{desc}{R}  {marker}")
    print(f"    {DIM}[enter] default = SIGTERM (15){R}")
    try:
        choice = input(f"\n  signal › ").strip() or "15"
    except (EOFError, KeyboardInterrupt):
        return None, None
    if choice in SIGNAL_MAP:
        name, sig, _ = SIGNAL_MAP[choice]
        return sig, name
    print(f"{RED}unknown signal{R}")
    return None, None


def kill_interactive():
    """
    Full interactive kill flow:
      search → pick match → pick signal → confirm → execute → report
    """
    print(f"\n{RED}{B}━━━ process killer ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}")
    print(f"  {DIM}enter a name (partial ok) or PID to find processes{R}\n")

    try:
        target = input(f"  {WHITE}{B}search ›{R} ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{DIM}cancelled{R}")
        return

    if not target:
        return

    matches = find_procs(target)

    if not matches:
        print(f"\n  {RED}no process matching '{target}'{R}\n")
        return

    # ── show matches ──────────────────────────────────────────────────────────
    print(f"\n  {YELLOW}{B}found {len(matches)} match(es):{R}\n")
    now = time.time()
    rows = []
    for p in matches:
        try:
            with p.oneshot():
                name = p.name()
                pid  = p.pid
                stat = p.status()
                up   = now - p.create_time()
                rss  = p.memory_info().rss
                cpu  = p.cpu_percent(interval=None)
            rows.append((pid, name, stat, up, rss, cpu, p))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not rows:
        print(f"  {RED}processes disappeared before we could read them{R}\n")
        return

    print(f"  {'#':>3}  {'PID':>7}  {'NAME':<24}  {'STATUS':<10}  {'UPTIME':>12}  {'RSS':>9}")
    print(f"  {'─'*3}  {'─'*7}  {'─'*24}  {'─'*10}  {'─'*12}  {'─'*9}")
    for i, (pid, name, stat, up, rss, cpu, _) in enumerate(rows, 1):
        stat_c = GREEN if stat == "running" else DIM
        known_c = CYAN if name in KNOWN_APPS else WHITE
        print(f"  {DIM}{i:>3}{R}  {DIM}{pid:>7}{R}  {known_c}{name:<24}{R}  "
              f"{stat_c}{stat:<10}{R}  {DIM}{fmt_uptime(up):>12}{R}  {fmt_bytes(rss):>9}")

    print()

    # ── pick target(s) ────────────────────────────────────────────────────────
    if len(rows) == 1:
        selected = [rows[0]]
        print(f"  {DIM}single match — auto-selected{R}")
    else:
        try:
            raw = input(f"  pick # (or 'all' to select all, blank=cancel) › ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}cancelled{R}")
            return

        if not raw:
            return

        if raw == "all":
            selected = rows
        else:
            parts = [x.strip() for x in raw.replace(",", " ").split()]
            selected = []
            for part in parts:
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(rows):
                        selected.append(rows[idx])
                    else:
                        print(f"  {RED}no entry #{part}{R}")
            if not selected:
                print(f"  {DIM}nothing selected{R}")
                return

    # ── pick signal ───────────────────────────────────────────────────────────
    sig, sig_name = _pick_signal()
    if sig is None:
        return

    # ── kill children too? ────────────────────────────────────────────────────
    include_children = False
    if sig in (signal.SIGTERM, signal.SIGKILL):
        include_children = _confirm("also kill child processes?")

    # ── confirmation ──────────────────────────────────────────────────────────
    print(f"\n  {BG_RED}{B} CONFIRM {R}  about to send {RED}{B}{sig_name}{R} to:")
    for pid, name, *_ in selected:
        child_note = f"  {DIM}+ children{R}" if include_children else ""
        print(f"    {RED}✕{R}  {CYAN}{name}{R}  {DIM}(pid {pid}){R}{child_note}")

    if not _confirm(f"proceed with {sig_name}?"):
        print(f"  {DIM}aborted — nothing was killed{R}\n")
        return

    # ── execute ───────────────────────────────────────────────────────────────
    print()
    total_ok = 0
    total_fail = 0

    for pid, name, stat, up, rss, cpu, proc in selected:
        result = _send_signal(proc, sig, sig_name, include_children)
        for ok_pid, ok_name in result["ok"]:
            print(f"  {GREEN}✓{R}  sent {B}{sig_name}{R} → {CYAN}{ok_name}{R}  {DIM}(pid {ok_pid}){R}")
            total_ok += 1
        for fail_pid, reason in result["fail"]:
            print(f"  {RED}✗{R}  pid {fail_pid}  {DIM}{reason}{R}")
            total_fail += 1

    # ── verify they're gone (only for kill signals) ───────────────────────────
    if sig in (signal.SIGTERM, signal.SIGKILL):
        time.sleep(0.5)
        still_alive = []
        for pid, name, *_, proc in selected:
            try:
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    still_alive.append((pid, name, proc))
            except psutil.NoSuchProcess:
                pass

        if still_alive and sig == signal.SIGTERM:
            print(f"\n  {YELLOW}⚠  {len(still_alive)} process(es) still alive after SIGTERM{R}")
            if _confirm("force-kill them with SIGKILL?"):
                for pid, name, proc in still_alive:
                    try:
                        proc.kill()
                        print(f"  {RED}☠{R}  SIGKILL → {CYAN}{name}{R}  {DIM}(pid {pid}){R}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"  {RED}✗{R}  pid {pid}  {DIM}{e}{R}")
        elif not still_alive:
            print(f"\n  {GREEN}✓ all targeted processes are gone{R}")

    print(f"\n  {DIM}summary: {GREEN}{total_ok} sent{R}{DIM}  ·  {RED}{total_fail} failed{R}\n")


def kill_quick(target: str, force: bool = False):
    """
    Non-interactive quick kill: swordwatch.py kill <name|pid> [--force]
    Skips signal picker — uses SIGTERM (or SIGKILL if --force).
    """
    matches = find_procs(target)
    if not matches:
        print(f"{RED}no process matching '{target}'{R}")
        return

    sig      = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"

    print(f"\n{RED}{B}quick kill — {sig_name}{R}\n")
    for p in matches:
        try:
            name = p.name()
            pid  = p.pid
            p.send_signal(sig)
            print(f"  {GREEN}✓{R}  {sig_name} → {CYAN}{name}{R}  {DIM}(pid {pid}){R}")
        except psutil.NoSuchProcess:
            print(f"  {DIM}pid {p.pid} already gone{R}")
        except psutil.AccessDenied:
            print(f"  {RED}✗{R}  pid {p.pid}  access denied — try sudo")

    print()


def kill_batch_interactive():
    """
    Kill multiple apps at once from a checklist of currently running known apps.
    """
    procs = collect_processes(filter_known=False)
    procs.sort(key=lambda x: x["name"])

    print(f"\n{RED}{B}━━━ batch kill ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}")
    print(f"  {DIM}enter comma-separated numbers to kill multiple at once{R}\n")

    print(f"  {'#':>3}  {'PID':>7}  {'NAME':<24}  {'CPU':>7}  {'RSS':>9}  {'UPTIME':>12}")
    print(f"  {'─'*3}  {'─'*7}  {'─'*24}  {'─'*7}  {'─'*9}  {'─'*12}")

    for i, p in enumerate(procs, 1):
        known_c = CYAN if p['name'] in KNOWN_APPS else WHITE
        cpu_c   = GREEN if p['cpu'] < 5 else YELLOW if p['cpu'] < 30 else RED
        print(f"  {DIM}{i:>3}{R}  {DIM}{p['pid']:>7}{R}  {known_c}{p['name']:<24}{R}  "
              f"{cpu_c}{p['cpu']:>6.1f}%{R}  {fmt_bytes(p['rss']):>9}  {DIM}{fmt_uptime(p['up']):>12}{R}")

    print()
    try:
        raw = input(f"  {WHITE}{B}pick numbers (e.g. 1,3,7) or 'cancel' ›{R} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{DIM}cancelled{R}")
        return

    if not raw or raw == "cancel":
        return

    parts = [x.strip() for x in raw.replace(" ", ",").split(",")]
    selected = []
    for part in parts:
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(procs):
                selected.append(procs[idx])

    if not selected:
        print(f"  {DIM}nothing selected{R}")
        return

    sig, sig_name = _pick_signal()
    if sig is None:
        return

    print(f"\n  {BG_RED}{B} CONFIRM {R}  {sig_name} → {len(selected)} process(es):")
    for p in selected:
        print(f"    {RED}✕{R}  {CYAN}{p['name']}{R}  {DIM}(pid {p['pid']}){R}")

    if not _confirm("proceed?"):
        print(f"  {DIM}aborted{R}\n")
        return

    print()
    for item in selected:
        try:
            item["proc"].send_signal(sig)
            print(f"  {GREEN}✓{R}  {sig_name} → {CYAN}{item['name']}{R}  {DIM}(pid {item['pid']}){R}")
        except psutil.NoSuchProcess:
            print(f"  {DIM}pid {item['pid']} already gone{R}")
        except psutil.AccessDenied:
            print(f"  {RED}✗{R}  pid {item['pid']}  access denied — try sudo")
    print()


# ── existing views (unchanged) ────────────────────────────────────────────────

def view_dashboard(sort_by: str = "cpu", filter_known: bool = False):
    for p in psutil.process_iter():
        try: p.cpu_percent(interval=None)
        except: pass
    time.sleep(0.8)
    print(f"{DIM}live dashboard — Ctrl+C to return to menu{R}\n")
    time.sleep(0.4)
    try:
        while True:
            procs = collect_processes(filter_known)
            if sort_by == "cpu":
                procs.sort(key=lambda x: x["cpu"], reverse=True)
            elif sort_by == "mem":
                procs.sort(key=lambda x: x["rss"], reverse=True)
            elif sort_by == "time":
                procs.sort(key=lambda x: x["up"], reverse=True)

            vm    = psutil.virtual_memory()
            cpu_g = psutil.cpu_percent(interval=None)
            swap  = psutil.swap_memory()

            lines = [CLR]
            lines.append(f"{CYAN}{B}swordwatch{R}{DIM} — live · {datetime.now().strftime('%H:%M:%S')}{R}  "
                         f"[sort: {YELLOW}{sort_by}{R}]  "
                         f"[filter: {'known apps' if filter_known else 'all procs'}]")
            lines.append("")
            lines.append(
                f"  {B}cpu{R}  {cpu_bar(cpu_g, 20)}   "
                f"{B}ram{R}  {mem_bar(vm.percent, 20)}  {fmt_bytes(vm.used)}/{fmt_bytes(vm.total)}   "
                f"{B}swap{R} {mem_bar(swap.percent, 10)}  {fmt_bytes(swap.used)}/{fmt_bytes(swap.total)}"
            )
            lines.append("")
            hdr = (f"  {'PID':>7}  {'NAME':<22} {'CPU':>7}  {'MEM%':>6}  "
                   f"{'RSS':>9}  {'UPTIME':>12}  {'THR':>4}  {'STATUS':<10}")
            lines.append(f"{B}{WHITE}{hdr}{R}")
            lines.append(f"  {'─'*7}  {'─'*22} {'─'*7}  {'─'*6}  {'─'*9}  {'─'*12}  {'─'*4}  {'─'*10}")

            for p in procs[:40]:
                cpu_c  = GREEN if p['cpu'] < 5 else YELLOW if p['cpu'] < 30 else RED
                mem_c  = GREEN if p['mem_p'] < 2 else YELLOW if p['mem_p'] < 10 else RED
                name   = p['name'][:22]
                stat_c = GREEN if p['stat'] == 'running' else DIM
                name_c = CYAN if p['name'] in KNOWN_APPS else WHITE
                lines.append(
                    f"  {DIM}{p['pid']:>7}{R}  {name_c}{name:<22}{R} "
                    f"{cpu_c}{p['cpu']:>6.1f}%{R}  "
                    f"{mem_c}{p['mem_p']:>5.1f}%{R}  "
                    f"{fmt_bytes(p['rss']):>9}  "
                    f"{DIM}{fmt_uptime(p['up']):>12}{R}  "
                    f"{DIM}{p['thr']:>4}{R}  "
                    f"{stat_c}{p['stat']:<10}{R}"
                )
            lines.append(f"\n  {DIM}total: {len(procs)} · shown: {min(40,len(procs))} · "
                         f"known apps in {CYAN}cyan{R}{DIM}{R}")
            print("\n".join(lines), flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{DIM}dashboard paused{R}")


def view_deep(pid_or_name: str):
    proc = None
    target = pid_or_name.strip()
    if target.isdigit():
        try:
            proc = psutil.Process(int(target))
        except psutil.NoSuchProcess:
            print(f"{RED}no process with PID {target}{R}")
            return
    else:
        for p in psutil.process_iter(['name', 'pid']):
            try:
                if target.lower() in p.info['name'].lower():
                    proc = p
                    break
            except: pass
        if not proc:
            print(f"{RED}no process matching '{target}'{R}")
            return
    try:
        with proc.oneshot():
            pid     = proc.pid
            name    = proc.name()
            status  = proc.status()
            created = datetime.fromtimestamp(proc.create_time())
            uptime  = time.time() - proc.create_time()
            cpu_p   = proc.cpu_percent(interval=0.5)
            mem     = proc.memory_info()
            mem_p   = proc.memory_percent()
            thr     = get_threads(proc)
            cmd     = get_cmdline(proc)
            try: cwd  = proc.cwd()
            except: cwd = "—"
            try: user = proc.username()
            except: user = "—"
            try: nice = proc.nice()
            except: nice = "—"
            try: ctx  = proc.num_ctx_switches()
            except: ctx = None

        files = get_open_files(proc)
        conns = get_connections(proc)
        kids  = get_children(proc)
    except psutil.NoSuchProcess:
        print(f"{RED}process disappeared{R}")
        return

    print(f"\n{CYAN}{B}━━━ deep inspect ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}")
    print(f"  {B}name{R}        {CYAN}{name}{R}  {DIM}(pid {pid}){R}")
    print(f"  {B}status{R}      {GREEN if status=='running' else DIM}{status}{R}")
    print(f"  {B}user{R}        {user}")
    print(f"  {B}started{R}     {created.strftime('%Y-%m-%d %H:%M:%S')}  {DIM}({fmt_uptime(uptime)} ago){R}")
    print(f"  {B}command{R}     {DIM}{cmd[:100]}{R}")
    print(f"  {B}cwd{R}         {DIM}{cwd}{R}")
    print(f"  {B}nice{R}        {nice}")
    print()
    print(f"  {B}cpu%{R}        {cpu_bar(cpu_p, 20)}")
    print(f"  {B}mem%{R}        {mem_bar(mem_p, 20)}")
    print(f"  {B}rss{R}         {fmt_bytes(mem.rss)}  {DIM}(resident set){R}")
    print(f"  {B}vms{R}         {fmt_bytes(mem.vms)}  {DIM}(virtual){R}")
    print(f"  {B}threads{R}     {thr}")
    if ctx:
        print(f"  {B}ctx switches{R} voluntary={ctx.voluntary}  involuntary={ctx.involuntary}")
    if kids:
        print(f"\n{YELLOW}{B}  children ({len(kids)}){R}")
        for k in kids[:10]:
            try: print(f"    {DIM}{k.pid:>7}{R}  {k.name()}")
            except: pass
        if len(kids) > 10:
            print(f"    {DIM}... and {len(kids)-10} more{R}")
    if files:
        print(f"\n{YELLOW}{B}  open files ({len(files)}){R}")
        seen: set = set()
        for f in files[:20]:
            d = os.path.dirname(f)
            if d not in seen:
                print(f"    {DIM}{f}{R}")
                seen.add(d)
        if len(files) > 20:
            print(f"    {DIM}... and {len(files)-20} more{R}")
    else:
        print(f"\n  {DIM}open files: none visible (may need root){R}")
    if conns:
        print(f"\n{YELLOW}{B}  network connections ({len(conns)}){R}")
        for c in conns[:10]:
            print(f"    {DIM}{c}{R}")
    else:
        print(f"  {DIM}network: no connections{R}")

    # ── offer to kill from deep inspect ───────────────────────────────────────
    print(f"\n{RED}{'─'*58}{R}")
    try:
        action = input(f"  kill this process? [{RED}k{R}=kill  {YELLOW}s{R}=stop/pause  {DIM}enter{R}=skip] › ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        action = ""

    if action == "k":
        sig, sig_name = _pick_signal()
        if sig and _confirm(f"send {sig_name} to {name} (pid {pid})?"):
            try:
                proc.send_signal(sig)
                print(f"  {GREEN}✓{R}  {sig_name} sent to {CYAN}{name}{R}")
            except psutil.AccessDenied:
                print(f"  {RED}✗{R}  access denied — try sudo")
            except psutil.NoSuchProcess:
                print(f"  {DIM}process already gone{R}")
    elif action == "s":
        if _confirm(f"pause (SIGSTOP) {name} (pid {pid})?"):
            try:
                proc.send_signal(signal.SIGSTOP)
                print(f"  {YELLOW}⏸{R}  {CYAN}{name}{R} paused  {DIM}(resume with SIGCONT){R}")
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                print(f"  {RED}✗{R}  {e}")

    print(f"{CYAN}{'━'*58}{R}\n")


def view_known_only():
    procs = collect_processes(filter_known=True)
    print(f"\n{CYAN}{B}━━━ swordfish known apps running now ━━━━━━━━━━━━━━━━━━━━━{R}")
    if not procs:
        print(f"  {DIM}none of your apps are currently running{R}\n")
        return
    procs.sort(key=lambda x: x["up"], reverse=True)
    for p in procs:
        print(f"  {CYAN}{B}{p['name']:<20}{R} "
              f"pid={DIM}{p['pid']}{R}  "
              f"up={YELLOW}{fmt_uptime(p['up'])}{R}  "
              f"cpu={cpu_bar(p['cpu'], 8)}  "
              f"rss={fmt_bytes(p['rss'])}")
    print(f"\n  {DIM}{len(procs)} app(s) found{R}\n")


def view_top_hogs(n: int = 10):
    for p in psutil.process_iter():
        try: p.cpu_percent(interval=None)
        except: pass
    time.sleep(0.6)
    procs  = collect_processes(filter_known=False)
    by_cpu = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:n]
    by_mem = sorted(procs, key=lambda x: x["rss"], reverse=True)[:n]
    print(f"\n{RED}{B}━━━ top {n} cpu hogs ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}")
    for i, p in enumerate(by_cpu, 1):
        print(f"  {DIM}{i:>2}.{R} {CYAN}{p['name']:<22}{R} {cpu_bar(p['cpu'], 14)}  {DIM}pid {p['pid']}{R}")
    print(f"\n{MAGENTA}{B}━━━ top {n} memory hogs ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}")
    for i, p in enumerate(by_mem, 1):
        print(f"  {DIM}{i:>2}.{R} {CYAN}{p['name']:<22}{R} {mem_bar(p['mem_p'], 14)}  {fmt_bytes(p['rss'])}  {DIM}pid {p['pid']}{R}")
    print()


# ── menu ──────────────────────────────────────────────────────────────────────

def build_menu() -> str:
    return (
        f"\n"
        f"  {CYAN}{B}[1]{R}  live dashboard         {DIM}all processes, refreshes every 2s{R}\n"
        f"  {CYAN}{B}[2]{R}  live dashboard         {DIM}known apps only{R}\n"
        f"  {CYAN}{B}[3]{R}  my apps snapshot       {DIM}swordfish apps running right now{R}\n"
        f"  {CYAN}{B}[4]{R}  top hogs               {DIM}cpu + memory leaders{R}\n"
        f"  {CYAN}{B}[5]{R}  deep inspect           {DIM}full details on one process{R}\n"
        f"  {RED}{B}[6]{R}  kill a process         {DIM}search → pick → choose signal → confirm{R}\n"
        f"  {RED}{B}[7]{R}  batch kill             {DIM}pick multiple from list → kill together{R}\n"
        f"  {YELLOW}{B}[8]{R}  quick kill             {DIM}fast SIGTERM by name/pid{R}\n"
        f"  {CYAN}{B}[q]{R}  quit\n"
    )


def main():
    print_banner()
    for p in psutil.process_iter():
        try: p.cpu_percent(interval=None)
        except: pass

    while True:
        print(build_menu())
        try:
            choice = input(f"{WHITE}{B}swordwatch ›{R} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}bye{R}")
            sys.exit(0)

        if choice in ("q", "quit", "exit"):
            print(f"{DIM}bye{R}")
            break
        elif choice == "1":
            sort = input(f"  sort by [{YELLOW}cpu{R}/{YELLOW}mem{R}/{YELLOW}time{R}] (default cpu): ").strip() or "cpu"
            view_dashboard(sort_by=sort if sort in ("cpu","mem","time") else "cpu", filter_known=False)
        elif choice == "2":
            view_dashboard(sort_by="cpu", filter_known=True)
        elif choice == "3":
            view_known_only()
        elif choice == "4":
            view_top_hogs(10)
        elif choice == "5":
            t = input(f"  {DIM}enter pid or name:{R} ").strip()
            if t: view_deep(t)
        elif choice == "6":
            kill_interactive()
        elif choice == "7":
            kill_batch_interactive()
        elif choice == "8":
            t = input(f"  {DIM}name or pid to quick-kill:{R} ").strip()
            force = input(f"  force kill? (SIGKILL) [y/N]: ").strip().lower() == "y"
            if t: kill_quick(t, force=force)
        elif choice == "":
            pass
        else:
            print(f"{DIM}unknown option — type a number or q{R}")


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "kill":
        # swordwatch.py kill <name|pid> [--force]
        if len(args) < 2:
            print(f"{RED}usage: swordwatch.py kill <name|pid> [--force]{R}")
            sys.exit(1)
        print_banner()
        kill_quick(args[1], force="--force" in args)
    elif args:
        # swordwatch.py <name|pid>  — deep inspect shortcut
        print_banner()
        for p in psutil.process_iter():
            try: p.cpu_percent(interval=None)
            except: pass
        view_deep(args[0])
    else:
        main()
