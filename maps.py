#!/usr/bin/env python3
"""
maps.py — CLI entry point for knowledge_hub map tool.
Forwards args to knowledge_hub.py, mapping --origin → --city.

BUG4 FIX: added --query forwarding so place-pinning works from CLI.

Usage examples:
  python maps.py --city Dhaka --query cafe
  python maps.py --origin Dhaka --destination Chittagong --query restaurant
  python maps.py --city Sylhet --query park --limit 5
"""

import sys
import subprocess
import os

if __name__ == "__main__":
    base   = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(base, "knowledge_hub.py")

    args     = sys.argv[1:]
    new_args = []
    i = 0
    while i < len(args):
        if args[i] == "--origin":
            # BUG4 FIX: --origin still maps to --city (was already correct)
            new_args.append("--city")
            if i + 1 < len(args):
                new_args.append(args[i + 1])
                i += 1
        elif args[i] == "--places":
            # BUG4 FIX: --places maps to --query (new param name in knowledge_hub)
            new_args.append("--query")
            if i + 1 < len(args):
                new_args.append(args[i + 1])
                i += 1
        else:
            new_args.append(args[i])
        i += 1

    subprocess.run([sys.executable, script] + new_args)
