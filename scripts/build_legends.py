"""Restore selected historical people URLs with original, source-scoped articles.

This does not enable the former encyclopedia biography importer.
"""
import json
from build_buying_brief import ROOT, write, esc, ORIGIN, SITE


def main():
    data = json.loads((ROOT / 'data/people_profiles.json').read_text())
    cards = []
    for profile in data['profiles']:
        path = '/legends/' + profile['slug'] + '/'
        body = f'<nav aria-label="Breadcrumb"><a href="/discover/">Discover</a> · <a href="/legends/">People and ideas</a></nav><section class="hero"><p class="eyebrow">People behind the engineering</p><h1>{esc(profile["title"])}</h1><p class="lede">{esc(profile["intro"])}</p></section><article class="card">'
        for heading, paragraph in profile['sections']:
            body += f'<section><h2>{esc(heading)}</h2><p>{esc(paragraph)}</p></section>'
        body += '<h2>Read the primary sources</h2><ul>'
        for title, url, scope in profile['sources']:
            body += f'<li><a href="{esc(url, quote=True)}">{esc(title)}</a><p>{esc(scope)}</p></li>'
        body += f'</ul><p class="note">By MotorJury · source check {data["checked_at"]}. Original AI-assisted editorial synthesis of the linked records. Interpretations are identified above. Manufacturer accounts describe their own work; no interview, road test or specialist endorsement is claimed.</p></article><section class="card"><h2>Follow the design question</h2><ul>'
        body += ''.join(f'<li><a href="{url}">{esc(title)}</a></li>' for title, url in profile['related']) + '</ul></section>'
        schema = {'@context': 'https://schema.org', '@type': 'Article', 'headline': profile['title'],
                  'description': profile['description'], 'mainEntityOfPage': ORIGIN + path,
                  'about': {'@type': 'Person', 'name': profile['name']},
                  'author': {'@type': 'Organization', 'name': 'MotorJury', 'url': ORIGIN + '/'},
                  'publisher': {'@type': 'Organization', 'name': 'MotorJury', 'url': ORIGIN + '/'},
                  'datePublished': data['checked_at'], 'dateModified': data['checked_at'],
                  'citation': [source[1] for source in profile['sources']]}
        write(path, profile['title'], body, description=profile['description'], jsonld=[schema], og_type='article')
        cards.append(f'<article class="card"><h2><a href="{path}">{esc(profile["name"])}</a></h2><p>{esc(profile["description"])}</p></article>')
    write('/legends/', 'People and ideas behind the cars', '<section class="hero"><h1>People behind the engineering.</h1><p class="lede">Start with a design decision, then inspect the original account. This collection is being rebuilt one sourced profile at a time.</p></section>' + ''.join(cards))
    # The small navigation hub is useful to readers; wait for a broader collection
    # before offering it as a separate search destination.
    hub = SITE / 'legends/index.html'
    hub.write_text(hub.read_text().replace('</head>', '<meta name="robots" content="noindex,follow"></head>'))
    print(f'People profiles: {len(cards)} original articles; imported biographies remain withheld')


if __name__ == '__main__':
    main()
