"""Draw the brand mark (same shapes as the header logo) at every icon size the site needs.

Run from anywhere: python tools/make_icons.py. Writes static/icons/*, static/favicon.svg.
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static') + os.sep
os.makedirs(ROOT + 'icons', exist_ok=True)
S = 1024  # supersampled canvas
U = S / 32  # one viewBox unit


def gradient(size):
    """Diagonal gradient from the logo: #6a95ff (top-left) to #2f5bf0 (bottom-right)."""
    c1, c2 = (106, 149, 255), (47, 91, 240)
    img = Image.new('RGB', (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))
    return img


def mark(rounded):
    base = gradient(S).convert('RGBA')
    draw = ImageDraw.Draw(base)
    width = round(2.4 * U)

    def line(points):
        pts = [(x * U, y * U) for x, y in points]
        draw.line(pts, fill='white', width=width, joint='curve')
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill='white')

    line([(16, 8), (16, 19)])
    line([(11.5, 14.5), (16, 19), (20.5, 14.5)])
    line([(9.5, 23), (22.5, 23)])
    if rounded:
        mask = Image.new('L', (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=round(10 * U), fill=255)
        base.putalpha(mask)
    return base


rounded, square = mark(True), mark(False)
for size, name in ((512, 'icon-512.png'), (192, 'icon-192.png'), (96, 'icon-96.png'), (48, 'icon-48.png')):
    rounded.resize((size, size), Image.LANCZOS).save(ROOT + 'icons/' + name, optimize=True)
square.convert('RGB').resize((180, 180), Image.LANCZOS).save(ROOT + 'icons/apple-touch-icon.png', optimize=True)
rounded.resize((256, 256), Image.LANCZOS).save(ROOT + 'icons/favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])

svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="10" fill="url(#g)"/>'
       '<path d="M16 8v11m0 0-4.5-4.5M16 19l4.5-4.5M9.5 23h13" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
       '<defs><linearGradient id="g" x1="4" y1="2" x2="28" y2="30"><stop stop-color="#6a95ff"/><stop offset="1" stop-color="#2f5bf0"/></linearGradient></defs></svg>\n')
open(ROOT + 'favicon.svg', 'w', encoding='utf-8', newline='\n').write(svg)
for name in sorted(os.listdir(ROOT + 'icons')):
    print(name, os.path.getsize(ROOT + 'icons/' + name), 'bytes')
