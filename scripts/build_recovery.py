"""Recover exact catalogue identities after marque changes or the model-page cap.

Only catalogue-backed routes with a real page (and, if needed, exact roster
anchor) are emitted. Unknown models must continue to return 404.
"""
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
from build_library import slug

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = re.compile(r"-(?:ag|se|sa|spa|srl|plc|inc|ltd|llc|gmbh|nv|bv|cars|auto|automobiles|automotive|motors|motor-company|motor-corporation|company|corporation|group)$")


def build_redirects(raw, rows, site):
    identities = defaultdict(set)
    for row in rows:
        if row.get('q'):
            identities[row['q']].add(row['u'])
    proposals = defaultdict(set)
    for row in rows:
        proposals[f'/library/{slug(row["b"])}/{slug(row["n"])}/'].add(row['u'])
    for record in raw:
        targets = identities.get(record.get('q'), set())
        if len(targets) != 1:
            continue
        manufacturer = slug(record.get('m') or '')
        if manufacturer == 'x' or re.fullmatch(r'q\d+', manufacturer):
            continue
        aliases = {manufacturer}
        short = SUFFIX.sub('', manufacturer)
        # A shortened corporate label is an alias only when the model itself
        # names that marque. Do not infer brands from arbitrary first words.
        name = slug(record['n'])
        if name.startswith(short + '-'):
            aliases.add(short)
        for marque in aliases:
            proposals[f'/library/{marque}/{slug(record["n"])}/'].update(targets)
    result = {}
    pages = {}
    for source, targets in sorted(proposals.items()):
        if len(targets) != 1 or (site / source.strip('/') / 'index.html').exists():
            continue
        target = next(iter(targets))
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith('/library/') or target == source:
            continue
        page = site / parsed.path.strip('/') / 'index.html'
        if not page.is_file():
            continue
        if parsed.fragment:
            if page not in pages:
                pages[page] = page.read_text()
            if f'id="{parsed.fragment}"' not in pages[page]:
                continue
        result[source] = target
    return result


def main():
    site = ROOT / 'site'
    redirects = build_redirects(json.loads((ROOT / 'data/car_library.json').read_text()),
                               json.loads((site / 'assets/catalogue-data.json').read_text()), site)
    (site / 'assets/route-recovery.json').write_text(json.dumps(redirects, ensure_ascii=False, separators=(',', ':')))
    print(f'Catalogue recovery: {len(redirects)} exact routes; unknown identities remain 404')


if __name__ == '__main__':
    main()
