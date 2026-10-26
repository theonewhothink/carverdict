"""Consistent public identities and a citable index of the evidence we publish."""
import copy
import datetime
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = os.environ.get('SITE_ORIGIN', 'https://motorjury.com').rstrip('/')
esc = html.escape


def page_entities(title, description, path, extra=None, origin=ORIGIN):
    """Describe the publisher and page without inventing reviews or credentials."""
    origin = origin.rstrip('/')
    org_id, site_id = origin + '/#organization', origin + '/#website'
    canonical = origin + path
    organization = {
        '@context': 'https://schema.org', '@type': 'Organization', '@id': org_id,
        'name': 'MotorJury', 'url': origin + '/',
        'logo': {'@type': 'ImageObject', 'url': origin + '/icon-512.png',
                 'width': 512, 'height': 512},
        'description': 'A car catalogue, sourced design stories and practical used-car viewing guides.',
        'publishingPrinciples': origin + '/editorial-policy/',
        'correctionsPolicy': origin + '/editorial-policy/',
    }
    website = {
        '@context': 'https://schema.org', '@type': 'WebSite', '@id': site_id,
        'name': 'MotorJury', 'url': origin + '/', 'publisher': {'@id': org_id},
        'inLanguage': 'en',
    }
    webpage = {
        '@context': 'https://schema.org', '@type': 'WebPage', '@id': canonical + '#webpage',
        'name': title, 'description': description, 'url': canonical,
        'isPartOf': {'@id': site_id}, 'publisher': {'@id': org_id}, 'inLanguage': 'en',
    }
    blocks = [organization, website, webpage]
    for original in extra or []:
        node = copy.deepcopy(original)
        types = node.get('@type', [])
        types = [types] if isinstance(types, str) else types
        if set(types) & {'Article', 'Report', 'BlogPosting', 'Dataset'}:
            node.setdefault('@id', canonical + ('#dataset' if 'Dataset' in types else '#article'))
            node['publisher'] = {'@id': org_id}
            author = node.get('author')
            if isinstance(author, dict) and author.get('@type') == 'Organization' and author.get('name') == 'MotorJury':
                node['author'] = {'@id': org_id}
            if 'Dataset' not in types:
                node['mainEntityOfPage'] = {'@id': canonical + '#webpage'}
            webpage.setdefault('mainEntity', {'@id': node['@id']})
        blocks.append(node)
    if path == '/about/adir-trabelsi/':
        person = {'@context': 'https://schema.org', '@type': 'Person',
                  '@id': canonical + '#person', 'name': 'Adir Trabelsi', 'url': canonical,
                  'description': 'Publisher of MotorJury.'}
        webpage['about'] = {'@id': person['@id']}
        blocks.append(person)
    return blocks


def machine_guide(origin=ORIGIN):
    return f'''# MotorJury
> Car reference catalogue, original source-linked design stories and practical used-car viewing guides.

## Current scope
- The buying brief covers 2019–2020 United States Toyota RAV4 gasoline and Hybrid vehicles. It excludes the RAV4 Prime.
- Catalogue entries and reference photographs are not verified buying recommendations. Photographs may show a different generation or trim.
- Historical articles are AI-assisted desk research from the primary sources linked on each page. No road test, mechanic review or interview is implied.
- Automatic reliability scores and BUY/CAUTION/AVOID recommendations are suspended. Complaint and recall totals are not failure rates.
- Budget outputs use the reader's assumptions; they are not market-price estimates or repair predictions.
- Failed or unmatched public-record lookups are unavailable, not zero. Model-level recall campaigns do not establish VIN applicability or repair completion.

## Read and cite the underlying page
- {origin}/sources/ — evidence sources, snapshot downloads and citation guidance
- {origin}/methodology/ — record matching, scope and calculation limits
- {origin}/editorial-policy/ — research standards and corrections
- {origin}/about/ — publisher accountability and current coverage
- {origin}/discover/ — researched car design stories
- {origin}/guides/ — practical used-car reader guides
- {origin}/buying-brief/ — the 2019–2020 US RAV4 viewing brief
- {origin}/legends/mate-rimac/ — the BMW conversion and Concept_One story
- {origin}/catalogue-notes/ — catalogue coverage and photo attribution

When citing MotorJury, link to the specific page and retain its market, version and source-check date. A rebuild date is not a new source review. Use the primary documents for safety decisions and verify the actual VIN.
This optional file is a reading aid; it does not change robots.txt, indexing eligibility or search-engine requirements.
'''


def build_sources(write, root=ROOT, origin=ORIGIN):
    records = json.loads((root / 'data/pilot_records.json').read_text())['records']
    profiles = json.loads((root / 'data/collection_profiles.json').read_text())
    assets = root / 'site/assets'
    assets.mkdir(parents=True, exist_ok=True)
    export = {'name': 'MotorJury vehicle-record matching snapshots',
              'scope': 'A deliberately selected small set of US model-year records, not a representative reliability study.',
              'methodology': origin + '/methodology/', 'records': records}
    (assets / 'motorjury-evidence.json').write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n')
    rows, citations = [], []
    for record in records:
        cells = []
        for service in ('complaints', 'recalls'):
            check = record['checks'][service]
            count = check.get('count') if check.get('status') in ('matched', 'empty') else None
            label = f"{count:,}" if isinstance(count, int) else 'Unavailable'
            urls = check.get('urls', [])
            date = check.get('checked_at', '')[:10] or 'Not recorded'
            if urls:
                label = f'<a href="{esc(urls[0], quote=True)}">{label}</a>'
                citations.extend(urls)
            cells.append(f'<td>{label}<br><small>Checked {esc(date)}</small></td>')
        rows.append('<tr><th scope="row">' + esc(f"{record['year']} {record['make']} {record['model']}")
                    + '</th>' + ''.join(cells) + '</tr>')
    body = '''<nav aria-label="Breadcrumb"><a href="/">Home</a> · Sources &amp; research</nav>
<section class="collection-hero compact"><p class="eyebrow">Trace the evidence</p><h1>Check the source behind the answer.</h1>
<p class="lede">Find the records, dates and limitations behind MotorJury’s buying guides and car design stories.</p></section>
<article class="collection-story"><h2>What each source can establish</h2>
<p><a href="https://www.nhtsa.gov/nhtsa-datasets-and-apis">NHTSA datasets and APIs</a> provide US complaint reports and safety-recall campaign records. Complaints are reports, not verified independent failures. A campaign count does not show whether a particular VIN is affected or repaired.</p>
<p><a href="https://www.fueleconomy.gov/feg/findacar.shtml">The EPA vehicle finder</a> provides fuel-economy information for the listed version. Our buying budget needs the correct US MPG figure and your own driving and fuel-price assumptions.</p>
<p>Manufacturer archives document the manufacturer’s own projects. They help establish design and version history; they do not independently establish ownership quality.</p>
<h2 id="vehicle-record-checks">Inspect the matched vehicle records</h2>
<p>This small, deliberately selected set covers the current RAV4 pilot and the Lexus model-spelling check. It is not a market-wide comparison or a reliability ranking. Each service has its own matching result and check date.</p>
<div class="table-wrap"><table><caption>Dated US model-level response snapshots</caption><thead><tr><th scope="col">Vehicle identity</th><th scope="col">Complaint reports</th><th scope="col">Distinct recall campaigns</th></tr></thead><tbody>'''
    report_url = f'/reports/used-car-trap-years-{datetime.date.today().year}/'
    body += ''.join(rows) + '''</tbody></table></div>
<p><a href="/assets/motorjury-evidence.json">Download the evidence snapshots as JSON</a>. The download includes source-response URLs, matching status, dates, aliases and stored response hashes. Later source responses can change. Unavailable does not mean zero.</p>
<p><a href="MATCHING_AUDIT_URL">Read the model-spelling matching audit</a> · <a href="/buying-brief/">Use the RAV4 viewing brief</a> · <a href="/guides/complaint-counts-without-failure-rates/">Why counts are not failure rates</a></p>
<h2>Read the manufacturer archives</h2><ul>'''
    for profile in profiles['profiles']:
        for title, url, scope in profile['sources']:
            body += f'<li><a href="{esc(url, quote=True)}">{esc(title)}</a><p>{esc(profile["name"])}: {esc(scope)}</p></li>'
    body += '''</ul><h2 id="cite">How to cite MotorJury</h2>
<p>Cite the specific article title, MotorJury, its canonical URL and the source-check date shown on that page. For a record snapshot, also retain the vehicle identity, service and timestamp. A page rebuild is not a fresh review.</p>
<p>Keep the original primary-source link alongside an interpretation. Distinguish an editorial suggestion from a manufacturer statement, a recall notice from a support program, and a scenario from a market valuation.</p>
<h2>Who is accountable</h2><p><a href="/about/adir-trabelsi/">Adir Trabelsi is the publisher</a>. The work is AI-assisted desk research; no road test, owner interview or specialist review is claimed unless the relevant page records that work.</p>
<p><a href="/editorial-policy/">Editorial standards and corrections</a> · <a href="/contact/">Send a source-backed correction</a> · <a href="/catalogue-notes/">Catalogue and photo credits</a></p></article>'''
    body = body.replace('MATCHING_AUDIT_URL', report_url)
    dataset = {'@context': 'https://schema.org', '@type': 'Dataset',
               'name': export['name'], 'description': export['scope'],
               'url': origin + '/sources/#vehicle-record-checks',
               'creator': {'@id': origin + '/#organization'},
               'isBasedOn': sorted(set(citations)),
               'distribution': {'@type': 'DataDownload', 'encodingFormat': 'application/json',
                                'contentUrl': origin + '/assets/motorjury-evidence.json'}}
    write('/sources/', 'MotorJury sources, research and evidence snapshots', body,
          description='Trace MotorJury claims to NHTSA records, EPA information and manufacturer archives. Inspect dated evidence snapshots, scope and citation guidance.',
          jsonld=[dataset])
    (root / 'site/llms.txt').write_text(machine_guide(origin))


if __name__ == '__main__':
    from build_buying_brief import write
    build_sources(write)
    print('SEARCH PRESENCE: sourced research index, evidence export and current machine-reading guide built')
