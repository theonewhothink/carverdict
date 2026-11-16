"""Write the five translated home pages from the finished English home page.

Runs after polish.py and localize_jury.py. Each language home is a full translation
(site chrome from jury_i18n.CHROME, page text from home_i18n), indexable, and joined
with the English home in one hreflang cluster.
"""
import html
import json
import re
from pathlib import Path

from home_i18n import META, PATTERNS, TEXT
from jury_i18n import CHROME, LANGS, RTL

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
ORIGIN = __import__('os').environ.get('SITE_ORIGIN', 'https://motorjury.com').rstrip('/')
LOCALE = {'en': 'en_US', 'pt': 'pt_PT', 'es': 'es_ES', 'fr': 'fr_FR', 'de': 'de_DE', 'he': 'he_IL'}
SCRIPT = re.compile(r'<script\b.*?</script>', re.S)
HREFLANG = re.compile(r'<link rel="alternate" hreflang="[^"]+" href="[^"]+">')


def home(lang):
    return '/' if lang == 'en' else f'/{lang}/'


def cluster():
    tags = ''.join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{home(l)}">' for l in LANGS)
    return tags + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/">'


def say(text, lang):
    """Translate one visible string, or return it unchanged."""
    core = text.strip()
    if not core:
        return text
    local = TEXT.get(core, {}).get(lang)
    if local is None:
        for pattern, reps in PATTERNS:
            if re.match(pattern, core):
                local = re.sub(pattern, reps[lang], core)
                break
    if local is None:
        return text
    lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
    return lead + local + trail


def translate_markup(part, lang):
    part = re.sub(r'>([^<]+)<', lambda m: '>' + html.escape(say(html.unescape(m.group(1)), lang), quote=False) + '<', part)
    return re.sub(r'\b(alt|aria-label|placeholder|title)="([^"]*)"',
                  lambda m: f'{m.group(1)}="' + html.escape(say(html.unescape(m.group(2)), lang), quote=True) + '"', part)


def build(src, lang):
    # Chrome first (longest first, as for the jury pages), then the page text; scripts untouched.
    scripts = SCRIPT.findall(src)
    text = SCRIPT.sub('\0S\0', src)
    head, body = text.split('</head>', 1)
    # Page text first, while it is still English, so no pattern can catch a translated chrome string.
    body = translate_markup(body, lang)
    for english, local in sorted(CHROME[lang].items(), key=lambda kv: -len(kv[0])):
        body = body.replace(english, local)
    title, desc = META[lang]
    t, d = html.escape(title, quote=True), html.escape(desc, quote=True)
    head = re.sub(r'<title>.*?</title>', f'<title>{html.escape(title, quote=False)}</title>', head, count=1, flags=re.S)
    for attr, value in (('name="description"', d), ('property="og:title"', t), ('property="og:description"', d),
                        ('name="twitter:title"', t), ('name="twitter:description"', d)):
        head = re.sub(r'(<meta ' + attr + r' content=")[^"]*(")', lambda m: m.group(1) + value + m.group(2), head, count=1)
    head = re.sub(r'(<meta property="og:image:alt" content=")[^"]*(")',
                  lambda m: m.group(1) + html.escape(say('Ferrari F40 · catalogue photograph', lang), quote=True) + m.group(2), head, count=1)
    head = re.sub(r'<meta name="robots"[^>]*>', '', head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + ORIGIN + home(lang) + m.group(2), head, count=1)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + ORIGIN + home(lang) + m.group(2), head, count=1)
    head = re.sub(r'<meta property="og:locale"[^>]*>', '', HREFLANG.sub('', head))
    head = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]+">', '', head)
    head += f'<meta property="og:locale" content="{LOCALE[lang]}">' + cluster()
    text = head + '</head>' + body
    text = re.sub(r'<html lang="[^"]*"[^>]*>', f'<html lang="{lang}"' + (' dir="rtl"' if lang in RTL else '') + '>', text, count=1)
    text = text.replace('href="/jury/"', f'href="/{lang}/jury/"')
    for s in scripts:
        if 'application/ld+json' in s and '"@type":"WebPage"' in s:
            data = json.loads(re.search(r'>(.*)</script>', s, re.S).group(1))
            data.update({'@id': f'{ORIGIN}{home(lang)}#webpage', 'name': title, 'description': desc,
                         'url': f'{ORIGIN}{home(lang)}', 'inLanguage': lang})
            s = re.sub(r'>(.*)</script>', lambda m: '>' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '</script>', s, count=1, flags=re.S)
        text = text.replace('\0S\0', s, 1)
    return text


def main():
    en = SITE / 'index.html'
    src = en.read_text()
    src = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]+">', '', HREFLANG.sub('', src))
    if 'property="og:locale"' not in src:
        src = src.replace('</head>', f'<meta property="og:locale" content="{LOCALE["en"]}"></head>', 1)
    en.write_text(src.replace('</head>', cluster() + '</head>', 1))
    for lang in LANGS:
        if lang != 'en':
            (SITE / lang / 'index.html').write_text(build(src, lang))
    print(f'HOME LANGUAGES: {len(LANGS) - 1} translated home pages; hreflang cluster of {len(LANGS)}')


if __name__ == '__main__':
    main()
