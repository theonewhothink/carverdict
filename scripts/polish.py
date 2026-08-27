#!/usr/bin/env python3
"""polish.py — one normalising pass over every generated page.

The site is written by nine generators, each with its own HTML shell. Head tags,
landmarks and social cards therefore drifted: no favicon anywhere, a dark theme-colour on
a white site, no og:image on a single page, and no <main> or skip link for keyboard and
screen-reader users. Fixing nine shells by hand guarantees the tenth is missed, so the
normalisation happens once, here, after everything has been written.

Idempotent: every insertion checks for itself first, so re-running changes nothing.
Runs last in build.sh, before the dead-link gate.
"""
import glob
import os
import re
import sys

ORIGIN = os.environ.get("SITE_ORIGIN", "https://motorjury.com").rstrip("/")

ICONS = (
    '<link rel="icon" href="/favicon.ico" sizes="32x32">'
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
    '<link rel="mask-icon" href="/mask-icon.svg" color="#10233F">'
    '<link rel="manifest" href="/site.webmanifest">'
)
THEME = ('<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">'
         '<meta name="theme-color" content="#0B0D10" media="(prefers-color-scheme: dark)">')
PRECONNECT = ('<link rel="preconnect" href="https://pagead2.googlesyndication.com" crossorigin>'
              '<link rel="dns-prefetch" href="https://pagead2.googlesyndication.com">')
DEFAULT_OG = "/og/default.png"

RE_THEME = re.compile(r'<meta name="theme-color"[^>]*>')
RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="(.*?)"', re.S)
RE_CANON = re.compile(r'<link rel="canonical" href="([^"]+)"')
RE_HREFLANG = re.compile(r'<link rel="alternate" hreflang="[^"]+" href="[^"]+">')

ACCT_CHIP = '<div class="acct-host" data-account-chip></div>'

SOCIAL = [
    ("Instagram", "https://www.instagram.com/motorjury/",
     "M12 2.2c3.2 0 3.6 0 4.9.1 1.2.1 1.8.2 2.2.4.6.2 1 .5 1.4.9.4.4.7.8.9 1.4.2.4.4 1 .4 2.2.1 1.3.1 1.7.1 4.9s0 3.6-.1 4.9c-.1 1.2-.2 1.8-.4 2.2-.2.6-.5 1-.9 1.4-.4.4-.8.7-1.4.9-.4.2-1 .4-2.2.4-1.3.1-1.7.1-4.9.1s-3.6 0-4.9-.1c-1.2-.1-1.8-.2-2.2-.4-.6-.2-1-.5-1.4-.9-.4-.4-.7-.8-.9-1.4-.2-.4-.4-1-.4-2.2C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.9c.1-1.2.2-1.8.4-2.2.2-.6.5-1 .9-1.4.4-.4.8-.7 1.4-.9.4-.2 1-.4 2.2-.4C8.4 2.2 8.8 2.2 12 2.2zm0 5.3a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9zm0 7.4a2.9 2.9 0 1 1 0-5.8 2.9 2.9 0 0 1 0 5.8zm5.7-7.6a1 1 0 1 1-2.1 0 1 1 0 0 1 2.1 0z"),
    ("TikTok", "https://www.tiktok.com/@motorjury",
     "M16.6 5.8c-1-.7-1.6-1.8-1.8-3h-2.9v11.6a2.4 2.4 0 1 1-1.7-2.3V9.1a5.3 5.3 0 1 0 4.6 5.3V9.1c1 .7 2.3 1.1 3.6 1.1V7.3c-.6 0-1.2-.2-1.8-.5z"),
    ("Facebook", "https://www.facebook.com/motorjury",
     "M13.5 21v-8h2.7l.4-3.1h-3.1V7.9c0-.9.3-1.5 1.6-1.5h1.6V3.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.4-4 4.1v2.3H7.5V13h2.8v8h3.2z"),
    ("YouTube", "https://www.youtube.com/@motorjury",
     "M21.6 7.2c-.2-.9-.9-1.6-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4c-.9.2-1.6.9-1.8 1.8C2 8.8 2 12 2 12s0 3.2.4 4.8c.2.9.9 1.6 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4c.9-.2 1.6-.9 1.8-1.8.4-1.6.4-4.8.4-4.8s0-3.2-.4-4.8zM10 15.1V8.9l5.2 3.1-5.2 3.1z"),
]
SOCIAL_ROW = (
    '<div class="wrap"><div class="social-row"><span class="social-lbl">Follow MotorJury</span>'
    + "".join(
        '<a class="soc soc-%s" href="%s" rel="noopener me" target="_blank" aria-label="%s" '
        'title="%s"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" '
        'd="%s"/></svg></a>' % (n.lower(), u, n, n, d) for n, u, d in SOCIAL)
    + '<span class="social-share" data-share></span></div></div>')


def polish(path):
    s = open(path, encoding="utf-8").read()
    if "<head>" not in s and "<head " not in s:
        return False
    orig = s

    # 1. one correct theme-colour pair (the old single dark value painted a black bar
    #    above a white page in mobile Chrome)
    s = RE_THEME.sub("", s)
    head_add = THEME
    if "rel=\"icon\"" not in s:
        head_add += ICONS
    if "pagead2.googlesyndication.com\" crossorigin" not in s:
        head_add += PRECONNECT

    # 2. social + AI-citation cards. Not one page had an og:image before this pass.
    title = (RE_TITLE.search(s).group(1).strip() if RE_TITLE.search(s) else "MotorJury")
    desc_m = RE_DESC.search(s)
    canon_m = RE_CANON.search(s)
    if "og:image" not in s:
        head_add += f'<meta property="og:image" content="{ORIGIN}{DEFAULT_OG}">'
        head_add += '<meta property="og:image:width" content="1200">'
        head_add += '<meta property="og:image:height" content="630">'
    if "og:title" not in s:
        head_add += f'<meta property="og:title" content="{title}">'
    if "og:description" not in s and desc_m:
        head_add += f'<meta property="og:description" content="{desc_m.group(1)}">'
    if "og:url" not in s and canon_m:
        head_add += f'<meta property="og:url" content="{canon_m.group(1)}">'
    if "og:site_name" not in s:
        head_add += '<meta property="og:site_name" content="MotorJury">'
    if "og:type" not in s:
        head_add += '<meta property="og:type" content="website">'
    if "twitter:card" not in s:
        head_add += '<meta name="twitter:card" content="summary_large_image">'

    s = s.replace("<head>", "<head>" + head_add, 1)

    # 3. hreflang is emitted twice by the localiser on translated pages; duplicate
    #    alternates are a validity error that can void the whole cluster.
    tags = RE_HREFLANG.findall(s)
    if len(tags) != len(set(tags)):
        seen = set()
        def keep(m):
            t = m.group(0)
            if t in seen:
                return ""
            seen.add(t)
            return t
        s = RE_HREFLANG.sub(keep, s)

    # 4. landmarks: a skip link and a <main>, for every shell at once
    if 'class="skip"' not in s:
        s = re.sub(r"(<body[^>]*>)", r'\1<a class="skip" href="#content">Skip to content</a>', s, count=1)
    if "<main" not in s and "</header>" in s and "<footer" in s:
        head_part, rest = s.split("</header>", 1)
        body_part, foot = rest.rsplit("<footer", 1)
        s = head_part + "</header>" + '<main id="content">' + body_part + "</main>" + "<footer" + foot

    # 5. the account chip, the follow/share row and the scripts behind them. Nine
    #    generators write nine different shells; the header on eight of them had no way to
    #    sign in and no footer had a way to follow or share the page. Injecting here is the
    #    only place that reaches all of them at once, and it is server-rendered rather than
    #    built by script, so nothing shifts as the page settles.
    if "data-account-chip" not in s and "</header>" in s:
        s = s.replace("</div></header>", ACCT_CHIP + "</div></header>", 1) \
            if "</div></header>" in s else s.replace("</header>", ACCT_CHIP + "</header>", 1)
    # The VIN check is the site's highest-intent utility. Put it in every generator's
    # navigation, not only gen_site's shell, so all 10,000+ library pages pass authority
    # and real users can reach it without returning home.
    header = s.split("</header>", 1)[0] if "</header>" in s else ""
    if 'href="/vin-check/"' not in header and '<nav class="nav">' in s:
        s = s.replace('<nav class="nav">', '<nav class="nav"><a href="/vin-check/">VIN check</a>', 1)
    if "social-row" not in s and "</footer>" in s:
        # inside the footer's own wrapper where there is one, so it inherits the padding
        if "</div></footer>" in s:
            s = s.replace("</div></footer>", SOCIAL_ROW + "</div></footer>", 1)
        else:
            s = s.replace("</footer>", SOCIAL_ROW + "</footer>", 1)
    for src in ("/assets/account.js", "/assets/share.js", "/assets/tco.js", "/assets/geo.js"):
        if src not in s and "</body>" in s:
            s = s.replace("</body>", f'<script src="{src}" defer></script></body>', 1)

    # 6. structured data floor. Several generators emit none at all, which leaves a third of
    #    the site invisible to rich results and to the AI engines that read JSON-LD first.
    if "application/ld+json" not in s:
        import json as _json
        crumbs = []
        if canon_m:
            from urllib.parse import urlparse
            segs = [x for x in urlparse(canon_m.group(1)).path.split("/") if x]
            acc = ""
            crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"}]
            for i, seg in enumerate(segs, start=2):
                acc += "/" + seg
                crumbs.append({"@type": "ListItem", "position": i,
                               "name": seg.replace("-", " ").title(), "item": ORIGIN + acc + "/"})
        block = {"@context": "https://schema.org", "@type": "WebPage", "name": title,
                 "url": (canon_m.group(1) if canon_m else ORIGIN + "/"),
                 "isPartOf": {"@type": "WebSite", "name": "MotorJury", "url": ORIGIN + "/"},
                 "publisher": {"@type": "Organization", "name": "MotorJury",
                               "url": ORIGIN + "/", "logo": ORIGIN + "/icon-512.png"}}
        if desc_m:
            block["description"] = desc_m.group(1)
        blocks = [block]
        if len(crumbs) > 1:
            blocks.append({"@context": "https://schema.org", "@type": "BreadcrumbList",
                           "itemListElement": crumbs})
        tags = "".join('<script type="application/ld+json">%s</script>'
                       % _json.dumps(b, separators=(",", ":")) for b in blocks)
        s = s.replace("</head>", tags + "</head>", 1)

    if s != orig:
        open(path, "w", encoding="utf-8").write(s)
        return True
    return False


def main():
    pages = glob.glob("site/**/*.html", recursive=True)
    n = sum(1 for p in pages if polish(p))
    print(f"POLISH OK: {n}/{len(pages)} pages normalised "
          f"(icons, theme-colour, social cards, landmarks, account chip, follow row)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
