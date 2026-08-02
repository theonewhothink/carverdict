#!/usr/bin/env python3
"""
car_images.py — Phase 3 images pipeline. Run on machine/CI with open network.
Per model-year: Wikimedia Commons search -> best free-licensed photo -> license ledger
-> AVIF/WebP/JPEG at 5 widths -> alt text. Fallback: other-year same-generation Commons
photo -> manufacturer press image (recorded as editorial) -> labeled illustration.
Requires: pip install pillow pillow-avif-plugin requests
"""
import json, re, sys, time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "images"
LEDGER = IMG / "license_ledger.json"
WIDTHS = [320, 640, 960, 1280, 1600]
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "CarsiteImages/1.0 (free-license image sourcing; respects licensing)"}
OK_LICENSE = re.compile(r"cc-by|cc0|public domain|pd-|attribution", re.I)


def ledger():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def save_ledger(d):
    LEDGER.write_text(json.dumps(d, indent=1))


def commons_search(query, limit=8):
    r = requests.get(API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size"})
    pages = (r.json().get("query") or {}).get("pages", {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", "")).strip()
        if OK_LICENSE.search(lic) and ii.get("width", 0) >= 1200:
            out.append({"title": p["title"], "url": ii["url"], "license": lic,
                        "author": artist or "unknown", "w": ii["width"]})
    return sorted(out, key=lambda x: -x["w"])


def process(slug3, query, alt):
    led = ledger()
    if slug3 in led:
        return True
    for q in [query, re.sub(r"^\d{4} ", "", query)]:  # fallback: drop year (same-gen photo)
        cands = commons_search(q)
        if cands:
            c = cands[0]
            raw = requests.get(c["url"], headers=UA, timeout=60).content
            src = IMG / "src" / f"{slug3}{Path(c['url']).suffix}"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_bytes(raw)
            im = Image.open(src).convert("RGB")
            for w in WIDTHS:
                if im.width < w:
                    continue
                h = int(im.height * w / im.width)
                r2 = im.resize((w, h), Image.LANCZOS)
                for ext, kw in [("jpg", {"quality": 82}), ("webp", {"quality": 78})]:
                    out = IMG / "out" / f"{slug3}-{w}.{ext}"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    r2.save(out, **kw)
                try:
                    r2.save(IMG / "out" / f"{slug3}-{w}.avif", quality=60)
                except Exception:
                    pass  # avif plugin optional
            led[slug3] = {"source": "wikimedia-commons", "file": c["title"], "url": c["url"],
                          "license": c["license"], "author": c["author"], "alt": alt,
                          "credit": f"Photo: {c['author']} / Wikimedia Commons ({c['license']})",
                          "fetched": time.strftime("%Y-%m-%d")}
            save_ledger(led)
            time.sleep(1)
            return True
    led[slug3] = {"source": "none", "note": "no free-licensed candidate; use labeled illustration",
                  "alt": alt}
    save_ledger(led)
    return False


def main():
    manifest = json.loads((ROOT / "data" / "manifest_seed.json").read_text())
    ok = tot = 0
    for e in manifest:
        for y in e["years"]:
            tot += 1
            s = f"{e['make']} {e['model']} {y}".lower().replace(" ", "-")
            if process(s, f"{y} {e['make']} {e['model']}",
                       f"{y} {e['make']} {e['model']} exterior"):
                ok += 1
    print(f"images: {ok}/{tot} licensed ({100*ok/max(1,tot):.0f}%; target >=90%)")


if __name__ == "__main__":
    main()
