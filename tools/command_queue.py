#!/usr/bin/env python3
"""
Command Queue — run multiple shell commands sequentially with delays.
Each command is killed after its delay expires. Output is logged to stdout.

Usage:
  python3 command_queue.py "python3 maths/mathplot.py heart" "python3 maths/mathplot.py spiral" --delay 3
  python3 command_queue.py --json '[{"cmd":"...","delay":3},{"cmd":"...","delay":6}]'
  python3 command_queue.py --list "heart" "butterfly" "spiral" --delay 3
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def run_sequence(commands, default_delay=3, log_callback=None):
    """
    Run each command, wait `delay` seconds, then kill it.
    Returns list of result dicts.
    """
    results = []
    for i, item in enumerate(commands):
        cmd = item["cmd"]
        delay = item.get("delay", default_delay)
        name = item.get("name", f"Step {i+1}")

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{name}] Running: {cmd}")
        if log_callback:
            log_callback(f"[{ts}] [{name}] {cmd}", "start")

        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")

        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            cwd=str(BASE),
            env=env,
        )

        out_text = ""
        err_text = ""
        try:
            stdout, stderr = proc.communicate(timeout=delay)
            out_text = (stdout or b"").decode(errors="replace").strip()
            err_text = (stderr or b"").decode(errors="replace").strip()
            if out_text:
                print(f"  stdout: {out_text[:300]}")
            if err_text:
                print(f"  stderr: {err_text[:300]}")
        except subprocess.TimeoutExpired:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(0.4)
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            print(f"  [{name}] killed after {delay}s")

        result = {
            "name": name,
            "cmd": cmd,
            "delay": delay,
            "stdout": out_text[:500],
            "stderr": err_text[:500],
        }
        results.append(result)

        if log_callback:
            log_callback(
                f"[{ts}] [{name}] {'killed' if delay else 'done'} | "
                f"out={len(out_text)}b err={len(err_text)}b",
                "end",
            )

        # Gap before next command
        if i < len(commands) - 1:
            time.sleep(1)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run multiple commands sequentially with auto-kill delays"
    )
    parser.add_argument("commands", nargs="*", help="Commands to run")
    parser.add_argument("--delay", type=float, default=3,
                        help="Default seconds before each command is killed")
    parser.add_argument("--math-delay", type=float, default=40,
                        help="Delay for math/graph commands (default: 40)")
    parser.add_argument("--stock-delay", type=float, default=20,
                        help="Delay for stock commands (default: 20)")
    parser.add_argument("--crypto-delay", type=float, default=10,
                        help="Delay for crypto commands (default: 10)")
    parser.add_argument("--json", metavar="FILE_OR_STRING",
                        help="JSON file or string with commands array")
    parser.add_argument("--list", nargs="+", metavar="PRESET",
                        help="Shortcut: run mathplot presets as a sequence")
    parser.add_argument("--log", metavar="FILE",
                        help="Append log to file")
    args = parser.parse_args()

    # Build command list
    commands = []

    if args.list:
        # Shortcut: mathplot presets
        for p in args.list:
            commands.append({
                "cmd": f"python3 maths/mathplot.py {p}",
                "delay": args.math_delay,
                "name": f"Plot: {p}",
            })

    elif args.json:
        try:
            if os.path.exists(args.json):
                with open(args.json) as f:
                    raw = json.load(f)
            else:
                raw = json.loads(args.json)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        commands.append({"cmd": item, "delay": args.delay})
                    else:
                        commands.append(item)
            else:
                print("JSON must be an array of command objects or strings")
                sys.exit(1)
        except Exception as e:
            print(f"JSON error: {e}")
            sys.exit(1)
    else:
        for c in args.commands:
            commands.append({"cmd": c, "delay": args.delay})

    if not commands:
        parser.print_help()
        sys.exit(1)

    # Optional file logging
    def file_log(msg, kind):
        if args.log:
            with open(args.log, "a") as f:
                f.write(f"{msg}\n")

    print(f"Running {len(commands)} commands sequentially...")
    results = run_sequence(commands, log_callback=file_log)

    # Print summary
    print("\n=== Summary ===")
    for r in results:
        print(f"  {r['name']}: {r['cmd'][:60]}... {'killed' if r['delay'] else 'done'}")


if __name__ == "__main__":
    main()
