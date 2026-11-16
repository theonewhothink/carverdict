"""The language home pages are full translations in one hreflang cluster with the English home."""
import html
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from home_i18n import META, TEXT  # noqa: E402
from jury_i18n import LANGS, RTL  # noqa: E402

SITE = ROOT / 'site'
PREVIEW = os.environ.get('MOTORJURY_PREVIEW') == '1'


def visible(text):
    text = re.sub(r'<(script|style|svg)\b.*?</\1>', ' ', text.split('<body', 1)[-1], flags=re.S)
    return [html.unescape(x.strip()) for x in re.findall(r'>([^<]+)<', text) if x.strip()]


@unittest.skipUnless((SITE / 'pt/index.html').exists(), 'site not built')
class HomeLanguages(unittest.TestCase):
    def test_every_language_has_every_string(self):
        for lang in LANGS[1:]:
            self.assertIn(lang, META)
            for english, local in TEXT.items():
                self.assertIn(lang, local, english)

    def test_built_pages(self):
        sitemap = (SITE / 'sitemap-0.xml').read_text()
        for lang in LANGS:
            page = (SITE / ('index.html' if lang == 'en' else f'{lang}/index.html')).read_text()
            url = 'https://motorjury.com/' + ('' if lang == 'en' else f'{lang}/')
            self.assertEqual(len(re.findall(r'rel="alternate" hreflang=', page)), len(LANGS) + 1, lang)
            self.assertIn(f'<link rel="canonical" href="{url}">', page)
            self.assertIn(f'<loc>{url}</loc>', sitemap)
            if not PREVIEW:
                self.assertNotIn('noindex', page, lang)
            if lang == 'en':
                continue
            self.assertRegex(page, f'<html lang="{lang}"' + (' dir="rtl"' if lang in RTL else '') + '>')
            self.assertIn(f'"inLanguage":"{lang}"', page)
            left = [t for t in visible(page) if t in TEXT and TEXT[t][lang] != t]
            self.assertEqual(left, [], lang)


if __name__ == '__main__':
    unittest.main()
