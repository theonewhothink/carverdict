"""og_card.py — 1200x630 Open Graph PNG cards, generated locally with Pillow. Deterministic."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

BG = (11, 13, 16)
CARD = (18, 21, 26)
TEXT = (232, 234, 237)
MUTED = (138, 147, 158)
EV = (34, 211, 238)
ICE = (245, 158, 11)
GOOD = (52, 211, 153)
BAD = (248, 113, 113)
CAUTION = (245, 158, 11)


def _font(size):
    for p in FONT_DIRS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def og_card(out_path: Path, title: str, subtitle: str, score, verdict: str, is_ev: bool):
    accent = EV if is_ev else ICE
    vcol = {"BUY": GOOD, "AVOID": BAD, "CAUTION": CAUTION}.get(verdict, MUTED)
    im = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(im)
    # accent top bar + subtle grid
    d.rectangle([0, 0, 1200, 10], fill=accent)
    for x in range(0, 1200, 60):
        d.line([x, 10, x, 630], fill=(15, 18, 22), width=1)
    # brand
    d.text((70, 58), "CAR", font=_font(40), fill=TEXT)
    w = d.textlength("CAR", font=_font(40))
    d.text((70 + w, 58), "VERDICT", font=_font(40), fill=accent)
    d.text((70, 112), "TRUE COST · PROBLEMS · DATA VERDICT", font=_font(22), fill=MUTED)
    # title (wrap at ~24 chars)
    words, lines, cur = title.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > 24 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    y = 210
    for ln in lines[:3]:
        d.text((70, y), ln, font=_font(72), fill=TEXT)
        y += 86
    d.text((70, y + 8), subtitle[:70], font=_font(30), fill=MUTED)
    # score dial (simple ring) + verdict chip
    if score is not None:
        cx, cy, r = 1010, 300, 118
        d.arc([cx - r, cy - r, cx + r, cy + r], 120, 420, fill=(35, 42, 52), width=22)
        end = 120 + int(300 * (max(0, min(100, score)) / 100))
        d.arc([cx - r, cy - r, cx + r, cy + r], 120, end, fill=accent, width=22)
        s = str(int(score))
        sw = d.textlength(s, font=_font(84))
        d.text((cx - sw / 2, cy - 58), s, font=_font(84), fill=TEXT)
        sw = d.textlength("/100", font=_font(28))
        d.text((cx - sw / 2, cy + 34), "/100", font=_font(28), fill=MUTED)
        if verdict:
            vw = d.textlength(verdict, font=_font(40)) + 56
            d.rounded_rectangle([cx - vw / 2, cy + 96, cx + vw / 2, cy + 164], 14, fill=CARD, outline=vcol, width=3)
            d.text((cx - (vw - 56) / 2, cy + 108), verdict, font=_font(40), fill=vcol)
    d.text((70, 560), "NHTSA + EPA public data · estimates labeled", font=_font(24), fill=MUTED)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "PNG", optimize=True)
    return out_path
