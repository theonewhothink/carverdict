"""Refresh checked pilot evidence atomically; an outage retains dated prior evidence.

Complaint narratives are not published. Component counts may overlap.
"""
import hashlib
import json
import urllib.request
from collections import Counter
from pathlib import Path
from nhtsa_records import records

PATH = Path(__file__).resolve().parents[1] / 'data' / 'pilot_records.json'


def get(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MotorJury-evidence/1.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def refresh(path=PATH, getter=get):
    payload = json.loads(path.read_text())
    for record in payload['records']:
        checks = {kind: records(record['make'], record['model'], record['year'], kind, getter)
                  for kind in ('complaints', 'recalls')}
        if any(c['status'] not in ('matched', 'empty') for c in checks.values()):
            print(f"PILOT: retained prior dated evidence for {record['year']} {record['make']} {record['model']}")
            continue
        complaints = checks['complaints']
        raw = complaints.pop('results')
        counts = Counter(component.strip() for row in raw for component in (row.get('components') or '').split(',') if component.strip())
        complaints['components'] = counts.most_common()
        complaints['response_sha256'] = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        record['checks'] = checks
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n')
    temporary.replace(path)


if __name__ == '__main__':
    refresh()
