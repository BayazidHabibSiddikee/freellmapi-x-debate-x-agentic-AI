#!/usr/bin/env python3
# tools/image.py — takes screenshot and converts to stencil
# Works on Linux via maim + convert
# Usage: python image.py --prompt "Starry Night"

import sys, argparse
from PIL import Image, ImageDraw
import os, time, subprocess


def capture_and_draw(prompt: str = "Screenshot"):
    print(f"\u2192 Generating image of [{prompt}]")
    scale = 0.8
    threshold = 128

    screenshot_path = "/tmp/marin_screenshot.png"
    try:
        subprocess.run(["maim", "-s", screenshot_path], check=True)
    except FileNotFoundError:
        print("SPEAK: maim not installed. Run: sudo apt install maim")
        sys.exit(1)

    img = Image.open(screenshot_path).convert("L")
    os.remove(screenshot_path)

    img = img.resize((int(img.width * scale), int(img.height * scale)))

    im = Image.new("RGBA", (img.width, img.height), "white")
    draw = ImageDraw.Draw(im)

    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y)) < threshold:
                draw.point((x, y), fill="black")

    im.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screenshot to stencil art")
    parser.add_argument('--prompt', type=str, default="Screenshot",
                        help="Label for what's being captured")
    args = parser.parse_args()
    capture_and_draw(args.prompt)
