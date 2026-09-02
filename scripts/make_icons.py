#!/usr/bin/env python3
"""make_icons.py — the MotorJury mark and the whole icon set from one definition.

The gavel remains the jury, but the former road bar was too abstract at favicon size. It is
now a high-contrast car silhouette with two unmistakable wheels. The result still belongs
to the same navy-and-gold identity, while the automotive meaning survives at 16 pixels.

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
  <!-- the car is the mark: a big side profile with two heavy wheels reads as "car" at 16 px -->
  <path d="M40 300h84l58-92c10-16 27-26 46-26h96c20 0 39 10 50 27l58 91h40c22 0 40 18 40 40v52H40c-22 0-40-18-40-40v-12c0-22 18-40 40-40z" fill="#F4F7FB"/>
  <path d="M160 300l44-70c5-8 14-13 24-13h30v83zm120 0v-83h28c11 0 21 5 27 15l42 68z" fill="#122A4E"/>
  <circle cx="140" cy="392" r="62" fill="#071426"/><circle cx="140" cy="392" r="26" fill="#FFB02E"/>
  <circle cx="372" cy="392" r="62" fill="#071426"/><circle cx="372" cy="392" r="26" fill="#FFB02E"/>
  <!-- the jury: a gold gavel about to strike, small enough to stay an accent -->
  <g transform="rotate(-35 400 112)">
    <rect x="322" y="86" width="156" height="58" rx="24" fill="url(#gold)"/>
    <rect x="380" y="140" width="40" height="70" rx="18" fill="url(#gold)"/>
  </g>
</svg>
"""

MASK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <g fill="black">
    <path d="M40 300h84l58-92c10-16 27-26 46-26h96c20 0 39 10 50 27l58 91h40c22 0 40 18 40 40v52H40c-22 0-40-18-40-40v-12c0-22 18-40 40-40z"/>
    <circle cx="140" cy="392" r="62"/><circle cx="372" cy="392" r="62"/>
    <g transform="rotate(-35 400 112)">
      <rect x="322" y="86" width="156" height="58" rx="24"/>
      <rect x="380" y="140" width="40" height="70" rx="18"/>
    </g>
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
    # cannot cut the wheels or the gavel off
    k = 0.74 if maskable else 1.0
    cx = cy = S / 2

    def T(x, y):
        return (cx + (x - cx) * k, cy + (y - cy) * k)

    # the car first: body, cabin, two heavy wheels. Drawn big so it survives 16 px.
    road = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(road)
    white = (244, 247, 251, 255)
    rd.rounded_rectangle([0, 300, 512, 392], radius=40, fill=white)
    rd.polygon([(124, 302), (182, 208), (328, 208), (392, 302)], fill=white)
    rd.polygon([(160, 296), (204, 230), (258, 230), (258, 296)], fill=NAVY_TOP + (255,))
    rd.polygon([(280, 230), (308, 230), (350, 296), (280, 296)], fill=NAVY_TOP + (255,))
    for cxw in (140, 372):
        rd.ellipse([cxw - 62, 330, cxw + 62, 454], fill=NAVY_BOT + (255,))
        rd.ellipse([cxw - 26, 366, cxw + 26, 418], fill=AMBER + (255,))
    if k != 1.0:
        small = road.resize((int(S * k), int(S * k)), Image.LANCZOS)
        road = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        road.paste(small, (int((S - S * k) / 2), int((S - S * k) / 2)), small)
    img.alpha_composite(road)

    # the gavel accent, rotated -35 degrees about (400, 112)
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for i in range(S):
        gd.line([(i, 0), (i, S)], fill=lerp(GOLD_TOP, GOLD_BOT, i / S) + (255,))
    shape = Image.new("L", (S, S), 0)
    sd = ImageDraw.Draw(shape)
    sd.rounded_rectangle([322, 86, 478, 144], radius=24, fill=255)
    sd.rounded_rectangle([380, 140, 420, 210], radius=18, fill=255)
    shape = shape.rotate(35, resample=Image.BICUBIC, center=(400, 112))
    layer.paste(grad, (0, 0), shape)
    if k != 1.0:
        small = layer.resize((int(S * k), int(S * k)), Image.LANCZOS)
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        layer.paste(small, (int((S - S * k) / 2), int((S - S * k) / 2)), small)
    img.alpha_composite(layer)

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
