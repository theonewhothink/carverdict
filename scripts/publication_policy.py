"""Advertising eligibility is independent of indexing and fails closed.

Run after every HTML generator, including localisations. Templates cannot opt a
page into advertising; only the reviewed exact-path manifest can do so.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "data" / "publication_policy.json"
ADS_SCRIPT = re.compile(r'<script\b[^>]*>.*?</script>', re.I | re.S)
AD_UNIT = re.compile(r'<ins\b[^>]*class=["\'][^"\']*\badsbygoogle\b[^"\']*["\'][^>]*>.*?</ins>', re.I | re.S)


def load_policy(path=POLICY):
    p = json.loads(path.read_text())
    if not isinstance(p.get("ads_enabled"), bool) or not isinstance(p.get("ad_pages"), dict):
        raise ValueError("Invalid publication policy; refusing to publish")
    for url, review in p["ad_pages"].items():
        if not url.startswith("/") or "?" in url or not url.endswith("/"):
            raise ValueError("Advertising review requires an exact canonical path")
        if review.get("status") != "reviewed" or not review.get("reviewed_at") or not review.get("evidence"):
            raise ValueError("Advertising eligibility requires a recorded review")
    return p


def ad_allowed(url, policy):
    return policy["ads_enabled"] and url in policy["ad_pages"]


def strip_ads(text):
    text = AD_UNIT.sub("", text)
    return ADS_SCRIPT.sub(lambda m: "" if "adsbygoogle" in m.group(0).lower() else m.group(0), text)


def apply(site=ROOT / "site", policy=None):
    policy = policy or load_policy()
    changed = 0
    for f in site.rglob("*.html"):
        url = "/" + f.relative_to(site).as_posix().removesuffix("index.html")
        original = f.read_text()
        if not ad_allowed(url, policy):
            clean = strip_ads(original)
            if clean != original:
                f.write_text(clean)
                changed += 1
    return changed


def verify(site=ROOT / "site", policy=None):
    policy = policy or load_policy()
    failures = []
    for f in site.rglob("*.html"):
        url = "/" + f.relative_to(site).as_posix().removesuffix("index.html")
        if "adsbygoogle" in f.read_text().lower() and not ad_allowed(url, policy):
            failures.append(url)
    if failures:
        raise ValueError("Unreviewed pages request ads: " + ", ".join(failures[:8]))


if __name__ == "__main__":
    print(f"PUBLICATION: removed ads from {apply()} unapproved pages")
    verify()
