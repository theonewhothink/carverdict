"""Prepare a dated, reviewable media snapshot; never run this during publication.

Only public Commons metadata is requested. Missing permissions stay unresolved.
The selected filenames come from existing catalogue records, never name searches.
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = 'MotorJuryArchiveResearch/1.0 (+https://motorjury.com/contact/)'


def selected_rows(rows, credits, limit=24):
    """Prefer documented photos, then spread the selection over distinct identities."""
    distinct = {}
    for row in sorted(rows, key=lambda r: r['n'].casefold()):
        if row.get('p'):
            distinct.setdefault(row['p'].replace('_', ' '), row)
    values = list(distinct.values())
    documented = [r for r in values if r['p'].replace('_', ' ') in credits]
    picked = documented[:limit]
    remaining = [r for r in values if r not in picked]
    count = min(limit - len(picked), len(remaining))
    if count:
        picked += [remaining[round(i * (len(remaining) - 1) / max(count - 1, 1))] for i in range(count)]
    return picked


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value or ''))).strip()


def fetch_batch(filenames):
    params = {'action': 'query', 'format': 'json', 'redirects': '1', 'prop': 'imageinfo',
              'iiprop': 'extmetadata|url|size', 'iiurlwidth': '960',
              'titles': '|'.join('File:' + name for name in filenames)}
    url = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=35) as response:
        data = json.load(response)
    if 'error' in data:
        raise RuntimeError(data['error'].get('code', 'Commons API error'))
    found = {}
    aliases = {}
    for kind in ('normalized', 'redirects'):
        aliases.update({x['from']: x['to'] for x in data.get('query', {}).get(kind, [])})
    pages = {p['title']: p for p in data.get('query', {}).get('pages', {}).values()}
    for name in filenames:
        title = 'File:' + name
        for _ in range(5):
            if title not in aliases:
                break
            title = aliases[title]
        info = (pages.get(title, {}).get('imageinfo') or [{}])[0]
        meta = info.get('extmetadata', {})
        artist = plain(meta.get('Artist', {}).get('value'))
        licence = plain(meta.get('LicenseShortName', {}).get('value'))
        licence_url = html.unescape(meta.get('LicenseUrl', {}).get('value', ''))
        if licence_url.startswith('//'):
            licence_url = 'https:' + licence_url
        if not licence_url and licence.lower() in ('public domain', 'cc0'):
            licence_url = info.get('descriptionurl', '')
        if not artist or not licence or not licence_url.startswith('https://'):
            continue
        found[name] = {'author': artist, 'licence': licence, 'licence_url': licence_url,
                       'thumb': info.get('thumburl', info.get('url', '')),
                       'original_url': info.get('url', ''), 'original_width': info.get('width', 0),
                       'original_height': info.get('height', 0), 'page': info.get('descriptionurl', ''),
                       'checked_at': date.today().isoformat()}
    return found


def main():
    rows = json.loads((ROOT / 'site/assets/catalogue-data.json').read_text())
    credits = json.loads((ROOT / 'data/photo_credits.json').read_text())
    groups = {}
    for row in rows:
        groups.setdefault(row['b'], []).append(row)
    names = sorted({r['p'].replace('_', ' ') for members in groups.values()
                    for r in selected_rows(members, credits)} - credits.keys())
    result, failures = {}, []
    for offset in range(0, len(names), 40):
        batch = names[offset:offset + 40]
        for attempt in range(3):
            try:
                result.update(fetch_batch(batch))
                break
            except Exception as error:
                if attempt == 2:
                    failures.append({'offset': offset, 'reason': type(error).__name__ + ': ' + str(error)[:180]})
                else:
                    time.sleep(3 * (attempt + 1))
        print(f'BRAND_MEDIA: {min(offset + 40, len(names))}/{len(names)} requested; {len(result)} documented', flush=True)
        # Stop promptly on service-wide access refusals rather than hammering it.
        if len(failures) >= 2 and not result:
            break
        time.sleep(1)
    output = ROOT / 'verification/brand-media'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'brand_media_credits.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (output / 'harvest-report.json').write_text(json.dumps({'requested': len(names), 'documented': len(result),
                                                          'failures': failures}, indent=2))
    print(f'BRAND_MEDIA_COMPLETE: {len(result)} additional documented photographs; {len(failures)} failed batches')


if __name__ == '__main__':
    main()
