"""
generate_ico.py — Generates igris.ico from igris_icon.png for desktop packaging.
Run once before building: python generate_ico.py

Requires: Pillow (pip install Pillow)
"""

import os
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"
PNG_SOURCE = ASSETS_DIR / "igris_icon.png"
ICO_OUTPUT = ASSETS_DIR / "igris.ico"

# ICO sizes required for Windows
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def generate_ico():
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    if not PNG_SOURCE.exists():
        print(f"ERROR: Source PNG not found: {PNG_SOURCE}")
        sys.exit(1)

    print(f"Generating {ICO_OUTPUT} from {PNG_SOURCE}...")

    img = Image.open(PNG_SOURCE).convert("RGBA")
    icons = []
    for size in ICO_SIZES:
        resized = img.resize((size, size), Image.LANCZOS)
        icons.append(resized)

    # Save as multi-resolution ICO
    icons[0].save(
        str(ICO_OUTPUT),
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=icons[1:],
    )
    print(f"✅ Created: {ICO_OUTPUT}")
    print(f"   Sizes: {ICO_SIZES}")


if __name__ == "__main__":
    generate_ico()
