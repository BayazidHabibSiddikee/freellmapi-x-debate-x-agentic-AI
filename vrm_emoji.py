#!/usr/bin/env python3
"""
Quick VRM emotion controller — change avatar emotions from terminal.
Usage: python3 vrm_emoji.py <expression>
  happy, angry, sad, surprised, neutral, wink, thinking, laughing
  Or type 'cycle' to auto-cycle, 'random' for random emotions, 'list' for options.
"""
import sys, json, time, random, urllib.request

SERVER = "http://localhost:8766/api/expression"

EXPRESSIONS = ["happy", "angry", "sad", "surprised", "neutral", "wink", "thinking", "laughing"]

EMOJI = {
    "happy": "😊", "angry": "😠", "sad": "😢", "surprised": "😲",
    "neutral": "😐", "wink": "😉", "thinking": "🤔", "laughing": "😂"
}

def set_expression(name, intensity=None):
    body = {"expression": name}
    if intensity is not None:
        body["intensity"] = intensity
    req = urllib.request.Request(SERVER, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        emoji = EMOJI.get(name, "🎭")
        print(f"  {emoji}  {name}")
    except Exception as e:
        print(f"  ❌  Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 vrm_emoji.py <expression|cycle|random|list>")
        print(f"  Expressions: {', '.join(EXPRESSIONS)}")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        for e in EXPRESSIONS:
            print(f"  {EMOJI.get(e, '🎭')}  {e}")

    elif cmd == "cycle":
        print("Cycling emotions (Ctrl+C to stop)...")
        while True:
            for e in EXPRESSIONS:
                set_expression(e)
                time.sleep(2)

    elif cmd == "random":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(f"Random {count} emotions:")
        for _ in range(count):
            set_expression(random.choice(EXPRESSIONS))
            time.sleep(1)

    elif cmd in EXPRESSIONS:
        intensity = float(sys.argv[2]) if len(sys.argv) > 2 else None
        set_expression(cmd, intensity)

    else:
        print(f"Unknown: {cmd}. Use 'list' for available expressions.")
