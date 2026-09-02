#!/usr/bin/env python3
"""Fast production-build accessibility and structure gate.

The site is mostly generated HTML, so regressions can affect thousands of pages at once.
This deliberately checks the final output rather than individual templates.
"""
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser


class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.h1 = 0
        self.main = 0
        self.missing_alt = 0
        self.bad_lightbox_links = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        elif tag == "main":
            self.main += 1
        elif tag == "img" and "alt" not in a:
            self.missing_alt += 1
        elif tag == "a" and a.get("href") == "#" and "data-lb" in a:
            self.bad_lightbox_links += 1


def main():
    pages = [p for p in glob.glob("site/**/*.html", recursive=True) if not p.endswith("site/offline.html")]
    failures = []
    for path in pages:
        text = open(path, encoding="utf-8").read()
        parser = Audit()
        parser.feed(text)
        dupes = len(parser.ids) - len(set(parser.ids))
        issues = []
        if dupes:
            issues.append(f"duplicate_ids={dupes}")
        if parser.h1 != 1:
            issues.append(f"h1={parser.h1}")
        if parser.main != 1:
            issues.append(f"main={parser.main}")
        if parser.missing_alt:
            issues.append(f"images_without_alt={parser.missing_alt}")
        if parser.bad_lightbox_links:
            issues.append(f"hash_lightbox_links={parser.bad_lightbox_links}")
        if '$0<' in text or '$0–' in text or '$0 /' in text:
            issues.append("zero_price_placeholder")
        if "Loading owner responses" in text:
            issues.append("owner_responses_loading_placeholder")
        if "Rate your love" in text or "Ratings are kept on your device" in text:
            issues.append("retired_local_rating_system")
        if "class=\"model-story\"" in text:
            if "data-love=" not in text or "data-survey=" not in text:
                issues.append("incomplete_account_engagement")
            if "adsbygoogle.js" not in text:
                issues.append("biography_missing_adsense")
            # Check the reader-visible article copy, not HTML attributes such as
            # class="bio-card", which naturally contain an equals sign.
            story = re.search(r'<article class="model-story">(.*?)</article>', text, re.I | re.S)
            story_copy = re.sub(r"<[^>]+>", " ", story.group(1)) if story else ""
            fields = r"class|body(?:_style)?|engine|power|layout|transmission|production|assembly|designer|predecessor|successor|wheelbase|length|width|height|weight"
            if re.search(rf"\b(?:{fields})\s*=", story_copy, re.I):
                issues.append("raw_infobox_template_debris")
        if not re.search(r'<meta\s+name=["\']viewport["\']', text, re.I):
            issues.append("missing_viewport")
        if issues:
            failures.append((path, ", ".join(issues)))

    # Cross-page catalogue counts come from one de-duplicated dataset. These three public
    # surfaces used to disagree after every harvest.
    try:
        home = open("site/index.html", encoding="utf-8").read()
        library = open("site/library/index.html", encoding="utf-8").read()
        follow = open("site/follow/index.html", encoding="utf-8").read()
        hm = re.search(r'<span class="hh-kicker">([\d,]+) models', home)
        lm = re.search(r'<p class="sub"><b>([\d,]+)</b>', library)
        fm = re.search(r'The library — ([\d,]+) models from ([\d,]+) marques', follow)
        counts = [int(x.group(1).replace(",", "")) for x in (hm, lm, fm) if x]
        if len(counts) != 3 or len(set(counts)) != 1:
            failures.append(("catalogue counts", f"home/library/follow={counts}"))
        if "typical price" not in home or "/yr fuel + maintenance" not in home:
            failures.append(("site/index.html", "homepage_cards_missing_price_or_running_cost"))
        search = open("site/search/index.html", encoding="utf-8").read()
        if "typical price" not in search or "/yr insurance" not in search or "/yr depreciation" not in search:
            failures.append(("site/search/index.html", "search_cards_missing_ownership_costs"))
        libdata = json.load(open("site/assets/library-data.json", encoding="utf-8"))
        if not any(m[4] for b in libdata.values() for m in b.get("m", []) if len(m) > 4):
            failures.append(("site/assets/library-data.json", "library_cards_have_no_cost_summaries"))
    except Exception as e:
        failures.append(("cross-page QA", str(e)))

    print(f"final HTML QA: pages={len(pages)} failures={len(failures)}")
    for path, issue in failures[:30]:
        print(f"  {path}: {issue}")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
