#!/usr/bin/env python3
"""make_icons.py — the MotorJury mark and the whole icon set from one definition.

The old mark was a gold gavel on navy at three-quarter weight. It read as a smudge at
16 pixels, which is the only size a favicon is ever actually seen at, and its two shapes
merged into one at that scale. This version is drawn for the tab strip first: two shapes,
maximum contrast, thick enough that antialiasing cannot dissolve them, and a silhouette
(diagonal bar over a horizontal bar) that stays recognisable when it is nine pixels tall.

The gavel is the jury. The bar it strikes is the road. Amber on navy because at small
sizes hue matters less than luminance distance, and this pair has plenty.

Run:  python scripts/make_icons.py     (writes static/ and site/ icon files)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static"

NAVY_TOP = (18, 42, 78)
NAVY_BOT = (7, 20, 38)
GOLD_TOP = (255, 209, 102)
GOLD_BOT = (214, 150, 30)
AMBER = (255, 176, 46)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="MotorJury">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="#122A4E"/><stop offset="1" stop-color="#071426"/>
    </linearGradient>
    <linearGradient id="gold" x1="0.1" y1="0" x2="0.9" y2="1">
      <stop offset="0" stop-color="#FFD166"/><stop offset="1" stop-color="#D6961E"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#bg)"/>
  <!-- the gavel: one heavy head, one heavy handle, struck across the frame -->
  <g transform="rotate(-30 256 226)">
    <rect x="88" y="148" width="336" height="130" rx="46" fill="url(#gold)"/>
    <rect x="210" y="268" width="92" height="144" rx="42" fill="url(#gold)"/>
  </g>
  <!-- the road it lands on: a bar with a centre line, which is what stops the mark
       reading as a hammer and nothing else -->
  <rect x="56" y="396" width="400" height="64" rx="32" fill="#FFB02E"/>
  <rect x="146" y="420" width="62" height="16" rx="8" fill="#071426" opacity="0.88"/>
  <rect x="240" y="420" width="62" height="16" rx="8" fill="#071426" opacity="0.88"/>
  <rect x="334" y="420" width="62" height="16" rx="8" fill="#071426" opacity="0.88"/>
</svg>
"""

MASK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <g fill="black">
    <g transform="rotate(-30 256 226)">
      <rect x="88" y="148" width="336" height="130" rx="46"/>
      <rect x="210" y="268" width="92" height="144" rx="42"/>
    </g>
    <rect x="56" y="396" width="400" height="64" rx="32"/>
  </g>
</svg>
"""


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rounded_rect(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def draw_icon(size, maskable=False, transparent_bg=False):
    from PIL import Image, ImageDraw
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if not transparent_bg:
        bg = Image.new("RGBA", (S, S))
        bd = ImageDraw.Draw(bg)
        for y in range(S):
            bd.line([(0, y), (S, y)], fill=lerp(NAVY_TOP, NAVY_BOT, y / S) + (255,))
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                               radius=(0 if maskable else 112), fill=255)
        img.paste(bg, (0, 0), mask)

    # scale the artwork down inside a maskable icon so the platform's circular crop
    # cannot cut the gavel's head off
    k = 0.74 if maskable else 1.0
    cx = cy = S / 2

    def T(x, y):
        return (cx + (x - cx) * k, cy + (y - cy) * k)

    # gavel, rotated -30 degrees about (256, 226), drawn as polygons so the rotation is real
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for i in range(S):
        gd.line([(i, 0), (i, S)], fill=lerp(GOLD_TOP, GOLD_BOT, i / S) + (255,))
    shape = Image.new("L", (S, S), 0)
    sd = ImageDraw.Draw(shape)
    sd.rounded_rectangle([88, 148, 424, 278], radius=46, fill=255)
    sd.rounded_rectangle([210, 268, 302, 412], radius=42, fill=255)
    shape = shape.rotate(30, resample=Image.BICUBIC, center=(256, 226))
    layer.paste(grad, (0, 0), shape)

    if k != 1.0:
        small = layer.resize((int(S * k), int(S * k)), Image.LANCZOS)
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        layer.paste(small, (int((S - S * k) / 2), int((S - S * k) / 2)), small)
    img.alpha_composite(layer)

    road = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(road)
    rd.rounded_rectangle([56, 396, 456, 460], radius=32, fill=AMBER + (255,))
    # The centre line is what turns a hammer into a road, but below about 64 pixels the
    # dashes stop resolving and only muddy the bar. Draw them only where they can be seen.
    if size >= 64:
        for x in (146, 240, 334):
            rd.rounded_rectangle([x, 420, x + 62, 436], radius=8, fill=NAVY_BOT + (235,))
    if k != 1.0:
        small = road.resize((int(S * k), int(S * k)), Image.LANCZOS)
        road = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        road.paste(small, (int((S - S * k) / 2), int((S - S * k) / 2)), small)
    img.alpha_composite(road)

    return img.resize((size, size), Image.LANCZOS)


def og_card():
    """The default social card. Every share of a page without its own card uses this, so it
    has to state what the site is in one line at thumbnail size."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=lerp(NAVY_TOP, NAVY_BOT, y / H))
    icon = draw_icon(196)
    img.paste(icon, (84, 84), icon)

    def font(sz, bold=True):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if Path(p).exists():
                try:
                    return ImageFont.truetype(p, sz)
                except Exception:
                    pass
        return ImageFont.load_default()

    d.text((84, 320), "MotorJury", font=font(84), fill=(255, 255, 255))
    d.text((84, 424), "What that car really costs to own.", font=font(40), fill=(255, 209, 102))
    d.text((84, 486), "Price · depreciation · repairs · insurance · verdict,", font=font(30), fill=(190, 205, 225))
    d.text((84, 528), "computed from NHTSA and EPA public data.", font=font(30), fill=(190, 205, 225))
    d.rounded_rectangle([84, 596, 384, 604], radius=4, fill=(255, 176, 46))
    return img


def ico(path, img_sizes):
    imgs = [draw_icon(s) for s in img_sizes]
    imgs[0].save(path, format="ICO", sizes=[(s, s) for s in img_sizes])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "favicon.svg").write_text(SVG)
    (OUT / "mask-icon.svg").write_text(MASK)
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("WARNING: pillow missing; SVG icons written, PNGs left as they were")
        return 0

    for name, size in [("favicon-16x16.png", 16), ("favicon-32x32.png", 32),
                       ("favicon-48x48.png", 48), ("icon-96.png", 96),
                       ("icon-192.png", 192), ("icon-512.png", 512),
                       ("apple-touch-icon.png", 180)]:
        draw_icon(size).save(OUT / name)
    for name, size in [("maskable-192.png", 192), ("maskable-512.png", 512)]:
        draw_icon(size, maskable=True).save(OUT / name)
    ico(OUT / "favicon.ico", [16, 32, 48])

    (OUT / "og").mkdir(exist_ok=True)
    og_card().save(OUT / "og" / "default.png", quality=92)
    print("ICONS OK: favicon.svg, mask-icon.svg, 9 PNGs, favicon.ico, default OG card")
    return 0


if __name__ == "__main__":
    sys.exit(main())
