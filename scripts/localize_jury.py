"""Finish the Car Jury language pages after polish.py has added the shared site chrome.

Sets the document language and direction, translates the chrome around the game, gives
each language its own share image, and joins the six indexable jury pages in one hreflang
cluster. The translated game text itself is written by build_jury.py.
"""
import re
from pathlib import Path
from jury_i18n import CHROME, LANGS, PAGE, RTL, path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
ORIGIN = __import__('os').environ.get('SITE_ORIGIN', 'https://motorjury.com').rstrip('/')
LOCALE = {'en': 'en_US', 'pt': 'pt_PT', 'es': 'es_ES', 'fr': 'fr_FR', 'de': 'de_DE', 'he': 'he_IL'}
DATA = re.compile(r'<script type="application/json" data-jury-i18n>.*?</script>', re.S)


def cluster():
    tags = ''.join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{path(l)}">' for l in LANGS)
    return tags + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}{path("en")}">'


def finish(text, lang, indexable):
    data = DATA.search(text)
    keep = data.group(0) if data else ''
    if keep:
        text = text.replace(keep, '\0JURYDATA\0', 1)
    # Longest first, so a sentence is translated before any phrase inside it.
    for english, local in sorted(CHROME[lang].items(), key=lambda kv: -len(kv[0])):
        text = text.replace(english, local)
    text = text.replace('\0JURYDATA\0', keep, 1)
    text = re.sub(r'<html lang="[^"]*"[^>]*>', f'<html lang="{lang}"' + (' dir="rtl"' if lang in RTL else '') + '>', text, count=1)
    text = re.sub(r'("@type":"WebPage"[^<]*?"inLanguage":)"en"', r'\g<1>"' + lang + '"', text, count=1)
    image = f'{ORIGIN}/og/jury-{lang}.png'
    text = re.sub(r'(<meta property="og:image" content=")[^"]*(")', r'\g<1>' + image + r'\g<2>', text, count=1)
    text = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', r'\g<1>' + image + r'\g<2>', text, count=1)
    alt = PAGE[lang]['og_alt'].replace('"', '&quot;')
    text = re.sub(r'(<meta property="og:image:alt" content=")[^"]*(")', r'\g<1>' + alt + r'\g<2>', text, count=1)
    text = re.sub(r'<meta property="og:locale"[^>]*>', '', text)
    head = f'<meta property="og:locale" content="{LOCALE[lang]}">'
    if indexable:
        text = re.sub(r'<link rel="alternate" hreflang="[^"]+" href="[^"]+">', '', text)
        head += cluster()
    return text.replace('</head>', head + '</head>', 1)


def main():
    done = 0
    for lang in LANGS:
        for rest, indexable in (('/jury/', True), ('/jury/ranking/', False)):
            f = SITE / path(lang, rest).strip('/') / 'index.html'
            f.write_text(finish(f.read_text(), lang, indexable))
            done += 1
    print(f'JURY LANGUAGES: {done} pages finished; hreflang cluster of {len(LANGS)} jury pages')


if __name__ == '__main__':
    main()
