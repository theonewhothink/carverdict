"""The jury language pages are complete translations in one valid hreflang cluster."""
import html
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from jury_i18n import CHROME, JS, LANGS, PAGE, path  # noqa: E402

SITE = ROOT / 'site'


def visible(text):
    text = re.sub(r'<(script|style|noscript)\b.*?</\1>', ' ', text, flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', ' ', text))


class JuryLanguages(unittest.TestCase):
    def test_every_language_has_every_string(self):
        for lang in LANGS:
            self.assertEqual(set(JS[lang]), set(JS['en']), lang)
            self.assertEqual(set(PAGE[lang]), set(PAGE['en']), lang)
            self.assertEqual(len(PAGE[lang]['faq']), len(PAGE['en']['faq']), lang)
            if lang != 'en':
                self.assertEqual(set(CHROME[lang]), set(CHROME['pt']), lang)
            for key in JS['en']:
                self.assertEqual(set(re.findall(r'\{(\w+)\}', JS[lang][key])), set(re.findall(r'\{(\w+)\}', JS['en'][key])), (lang, key))

    @unittest.skipUnless((SITE / 'pt/jury/index.html').exists(), 'needs a built site')
    def test_built_pages_are_translated_and_clustered(self):
        english = {s for s in list(PAGE['en'].values()) if isinstance(s, str) and len(s) > 12 and '{' not in s}
        english |= {k for k in CHROME['pt'] if not k.startswith('>') and '&amp;' not in k and len(k) > 6}
        for lang in LANGS:
            text = (SITE / path(lang).strip('/') / 'index.html').read_text()
            self.assertIn(f'<html lang="{lang}"', text)
            if __import__('os').environ.get('MOTORJURY_PREVIEW') != '1':
                self.assertNotIn('noindex', text.split('</head>')[0], lang)
            self.assertIn(f'"@type":"WebPage"', text)
            self.assertRegex(text, r'"@type":"WebPage"[^<]*"inLanguage":"' + lang + '"')
            alternates = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', text)
            self.assertEqual(sorted(h for h, _ in alternates), sorted(LANGS + ['x-default']), lang)
            self.assertIn(f'<link rel="canonical" href="https://motorjury.com{path(lang)}">', text)
            self.assertIn(f'/og/jury-{lang}.png', text)
            if lang != 'en':
                words = visible(text)
                leftovers = [s for s in english if s in words]
                self.assertEqual(leftovers, [], lang)
            ranking = (SITE / path(lang, '/jury/ranking/').strip('/') / 'index.html').read_text()
            self.assertIn('noindex', ranking)
        self.assertIn(' dir="rtl"', (SITE / 'he/jury/index.html').read_text()[:400])


if __name__ == '__main__':
    unittest.main()
