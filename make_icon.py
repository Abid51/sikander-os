"""
Convert IGRIS PNG to .ico for desktop icon.
Run this ONCE before building with PyInstaller.
Usage: python make_icon.py
"""
from pathlib import Path
import urllib.request
import sys

def make_icon():
    try:
        from PIL import Image
    except ImportError:
        print("Installing Pillow…")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow'])
        from PIL import Image

    assets = Path('assets')
    assets.mkdir(exist_ok=True)

    # Look for source image
    src = None
    for name in ['igris_icon.png', 'igris.png', 'icon.png']:
        p = assets / name
        if p.exists():
            src = p
            break

    if src is None:
        print("ERROR: Put your IGRIS image in assets/igris_icon.png")
        return False

    img = Image.open(src).convert('RGBA')

    sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
    ico_path = assets / 'igris.ico'
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"✓ Icon saved: {ico_path}")
    return True

if __name__ == '__main__':
    make_icon()
