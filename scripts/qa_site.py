#!/usr/bin/env python3
"""Fast production-build accessibility and structure gate.

The site is mostly generated HTML, so regressions can affect thousands of pages at once.
This deliberately checks the final output rather than individual templates.
"""
import glob
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
    pages = glob.glob("site/**/*.html", recursive=True)
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
        if not re.search(r'<meta\s+name=["\']viewport["\']', text, re.I):
            issues.append("missing_viewport")
        if issues:
            failures.append((path, ", ".join(issues)))

    print(f"final HTML QA: pages={len(pages)} failures={len(failures)}")
    for path, issue in failures[:30]:
        print(f"  {path}: {issue}")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
