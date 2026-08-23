#!/usr/bin/env python3
# tools/alarm.py — runs as its own process
# Usage: python alarm.py --time "05:00"   OR   python alarm.py --time "7:30 AM"

import os, sys, time, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Suppress ALSA noise before any audio import
_dn = os.open(os.devnull, os.O_WRONLY)
_se = os.dup(2)
os.dup2(_dn, 2)
try:
    import arrow
    from pygame import mixer
finally:
    os.dup2(_se, 2)
    os.close(_se)
    os.close(_dn)


def normalize_time(time_str: str) -> str:
    t = time_str.strip()
    try:
        if t.lower().endswith("am") or t.lower().endswith("pm"):
            return arrow.get(t, "h:mm A").format("h:mm A")
        if ":" in t:
            parts = t.split(":")
            h, m = int(parts[0]), int(parts[1])
            ampm = "AM" if h < 12 else "PM"
            if h == 0: h = 12
            if h > 12: h -= 12
            return f"{h}:{m:02d} {ampm}"
        return ""
    except Exception:
        return ""


def run_alarm(time_str: str):
    alarm_time = normalize_time(time_str)
    if not alarm_time:
        print("SPEAK: Could not understand alarm time.")
        sys.exit(1)

    print(f"\u2192 Setting alarm for [{alarm_time}]")
    print(f"SPEAK: Alarm set for {alarm_time}.")
    sys.stdout.flush()

    # Fork to background so terminal isn't locked
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Child continues in background
    while True:
        now = arrow.now().format('h:mm A')
        if alarm_time.strip() == now.strip():
            print("SPEAK: Your alarm is going off!")
            sys.stdout.flush()
            try:
                root = Path(__file__).resolve().parent.parent
                alarm_file = root / 'alarm.wav'
                if alarm_file.exists():
                    mixer.init()
                    mixer.music.load(str(alarm_file))
                    mixer.music.play()
                    while mixer.music.get_busy():
                        time.sleep(1)
                else:
                    print("SPEAK: Alarm triggered! No alarm.wav found.")
            except Exception as e:
                print(f"SPEAK: Alarm triggered! Sound error: {e}")
            sys.stdout.flush()
            break
        time.sleep(5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Set a clock alarm")
    parser.add_argument('--time', type=str, required=True,
                        help='Alarm time (e.g. "05:00" or "7:30 AM")')
    args = parser.parse_args()
    run_alarm(args.time)
