"""og_card.py — 1200x630 Open Graph PNG cards, generated locally with Pillow. Deterministic.

Brand: white ground, navy ink, one gold accent — the same system as the site. The previous
version still rendered the pre-launch CARVERDICT wordmark on a near-black card.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

BG = (255, 255, 255)
WASH = (246, 248, 249)
NAVY = (16, 35, 63)
TEXT = (17, 20, 23)
MUTED = (107, 117, 128)
GOLD = (168, 117, 26)
GOOD = (27, 107, 74)
BAD = (158, 42, 42)
CAUTION = (168, 117, 26)


def _font(size, bold=True):
    for p in FONT_DIRS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wordmark(d, x, y, size=40):
    f = _font(size)
    d.text((x, y), "Motor", font=f, fill=NAVY)
    d.text((x + d.textlength("Motor", font=f), y), "Jury", font=f, fill=GOLD)


def og_card(out_path: Path, title: str, subtitle: str, score, verdict: str, is_ev: bool):
    vcol = {"BUY": GOOD, "AVOID": BAD, "CAUTION": CAUTION}.get(verdict, MUTED)
    im = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 12], fill=NAVY)
    d.rectangle([0, 12, 1200, 16], fill=GOLD)

    _wordmark(d, 70, 56)
    d.text((70, 112), "TRUE COST  ·  PROBLEMS  ·  DATA VERDICT", font=_font(22), fill=MUTED)

    words, lines, cur = str(title).split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > 22 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    y = 205
    for ln in lines[:3]:
        d.text((70, y), ln, font=_font(70), fill=TEXT)
        y += 84
    d.text((70, y + 10), str(subtitle)[:70], font=_font(28), fill=MUTED)

    if score is not None:
        cx, cy, r = 1010, 300, 118
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WASH)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=135, end=405, fill=(226, 230, 234), width=18)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=135, end=135 + int(270 * (int(score) / 100)),
              fill=vcol, width=18)
        sf = _font(84)
        sw = d.textlength(str(score), font=sf)
        d.text((cx - sw / 2, cy - 56), str(score), font=sf, fill=TEXT)
        lf = _font(20)
        lw = d.textlength("/ 100", font=lf)
        d.text((cx - lw / 2, cy + 36), "/ 100", font=lf, fill=MUTED)
    if verdict:
        vf = _font(30)
        vw = d.textlength(str(verdict), font=vf)
        d.rectangle([1010 - vw / 2 - 22, 452, 1010 + vw / 2 + 22, 506], outline=vcol, width=3)
        d.text((1010 - vw / 2, 462), str(verdict), font=vf, fill=vcol)

    d.text((70, 560), "NHTSA complaints + recalls  ·  EPA fuel economy  ·  motorjury.com",
           font=_font(22), fill=MUTED)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "PNG", optimize=True)


def default_card(out_path: Path):
    """The card every page falls back to when it has no card of its own."""
    im = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 12], fill=NAVY)
    d.rectangle([0, 12, 1200, 16], fill=GOLD)
    _wordmark(d, 70, 70, 56)
    d.text((70, 210), "What does that car", font=_font(76), fill=TEXT)
    d.text((70, 296), "really cost to own?", font=_font(76), fill=TEXT)
    d.text((70, 410), "Per-model-year verdicts computed from NHTSA", font=_font(30), fill=MUTED)
    d.text((70, 452), "complaints, recalls and EPA fuel economy.", font=_font(30), fill=MUTED)
    d.rectangle([70, 528, 74, 578], fill=GOLD)
    d.text((96, 532), "motorjury.com", font=_font(30), fill=NAVY)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "PNG", optimize=True)
