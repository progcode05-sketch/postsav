"""Render tools/og-image.html to static/img/og-image.jpg (1200 x 630) with a headless Chromium-based browser.

Usage: python tools/make_og_image.py [path-to-chrome-or-edge]
Edit the brand name and tagline in tools/og-image.html first if SITE_NAME changes.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
BROWSERS = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']


def main():
    browser = sys.argv[1] if len(sys.argv) > 1 else next((b for b in BROWSERS if os.path.exists(b)), None)
    if not browser:
        sys.exit('No Chrome or Edge found; pass the path as an argument.')
    raw = Path(tempfile.mkdtemp()) / 'og.png'
    subprocess.run([browser, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1200,630', f'--screenshot={raw}',
                    (HERE / 'og-image.html').as_uri()], check=True, capture_output=True)
    target = HERE.parent / 'static' / 'img' / 'og-image.jpg'
    Image.open(raw).convert('RGB').crop((0, 0, 1200, 630)).save(target, 'JPEG', quality=88, optimize=True, progressive=True)
    print('wrote', target, target.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
