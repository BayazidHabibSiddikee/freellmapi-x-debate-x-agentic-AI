#!/usr/bin/env python3
# tools/tictactoe.py — wrapper that proxies to games/tiktaktoe.py
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_dn = os.open(os.devnull, os.O_WRONLY)
_se = os.dup(2)
os.dup2(_dn, 2)
try:
    from games.tiktaktoe import launch_game
finally:
    os.dup2(_se, 2)
    os.close(_se)
    os.close(_dn)

if __name__ == '__main__':
    launch_game()