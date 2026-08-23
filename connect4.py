#!/usr/bin/env python3
# tools/connect4.py — wrapper that proxies to games/connect4_ai.py or games/connect4_2p.py
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_dn = os.open(os.devnull, os.O_WRONLY)
_se = os.dup(2)
os.dup2(_dn, 2)
try:
    from games.connect4_ai import ConnectFour as ConnectFourAI
    from games.connect4_2p import ConnectFourTwoPlayer
finally:
    os.dup2(_se, 2)
    os.close(_se)
    os.close(_dn)

if __name__ == '__main__':
    is_2p = len(sys.argv) > 1 and sys.argv[1] == '--two'
    game = ConnectFourTwoPlayer() if is_2p else ConnectFourAI()
    game.start()