"""Search metadata derived from the page readers actually receive.

This pass never changes index eligibility, canonicals, dates, source claims or
ratings. It applies to held reference pages as well as reviewed articles.
"""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.in_title = False
        self.description = ''
        self.canonical = ''
        self.robots = []
        self.metas = {}
        self.image = None
        self.in_body = False
        self.in_main = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title' and not self.in_body:
            self.in_title = True
        if tag == 'body':
            self.in_body = True
        if tag == 'main':
            self.in_main = True
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical = a.get('href', '')
        if tag == 'meta':
            key = a.get('property') or a.get('name', '')
            self.metas[key.lower()] = a.get('content', '')
            if key.lower() == 'description':
                self.description = a.get('content', '')
            if key.lower() == 'robots':
                self.robots.append(a.get('content', '').lower())
        if tag == 'img' and self.in_body and self.image is None:
            src = a.get('src', '')
            width = a.get('width', '')
            sized_photo = width.isdigit() and int(width) >= 600
            # Model heroes deliberately omit fixed dimensions. Their explicit
            # priority and main-content placement distinguish them from icons.
            hero_photo = (not width and self.in_main and a.get('fetchpriority') == 'high'
                          and urlsplit(src).path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')))
            # Use a real content photograph, never a logo, avatar or tiny icon.
            if (a.get('alt', '').strip() and not a.get('aria-hidden') == 'true'
                    and not 'hidden' in a and (sized_photo or hero_photo)
                    and urlsplit(src).scheme in ('', 'https') and not src.startswith('//')):
                self.image = {'url': urljoin(self.canonical, src), 'alt': a['alt']}

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'main':
            self.in_main = False

    def handle_data(self, text):
        if self.in_title:
            self.title += text


META = re.compile(r'<meta\b[^>]*>', re.I)
LD = re.compile(r'(<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.I | re.S)


def meta_key(tag):
    parser = HTMLParser()
    found = []
    parser.handle_starttag = lambda _, attrs: found.extend(attrs)
    parser.feed(tag)
    attrs = dict(found)
    return (attrs.get('property') or attrs.get('name', '')).lower()


def normalise_search_metadata(text):
    if '</head>' not in text:
        return text
    page = PageMetadata()
    page.feed(text)
    if not page.title.strip() or not page.canonical:
        return text
    image = page.image['url'] if page.image else page.metas.get('og:image', '')
    values = {'og:title': page.title.strip(), 'og:url': page.canonical,
              'og:site_name': 'MotorJury', 'twitter:card': 'summary_large_image',
              'twitter:title': page.title.strip()}
    if page.description:
        values.update({'og:description': page.description,
                       'twitter:description': page.description})
    if image:
        values.update({'og:image': image, 'twitter:image': image})
    if page.image:
        values.update({'og:image:alt': page.image['alt'],
                       'twitter:image:alt': page.image['alt']})
    # Generic social-card dimensions do not describe a selected photograph.
    replace_keys = set(values)
    if page.image:
        replace_keys.update(('og:image:width', 'og:image:height'))
    head, rest = text.split('</head>', 1)
    head = META.sub(lambda match: '' if meta_key(match.group(0)) in replace_keys else match.group(0), head)
    tags = ''.join('<meta ' + ('property' if key.startswith('og:') else 'name')
                   + '="' + key + '" content="' + html.escape(value, quote=True) + '">'
                   for key, value in values.items())
    if not any(re.search(r'\b(?:noindex|none|noimageindex)\b', directives) for directives in page.robots):
        # A generous image preview is optional. Respect an existing deliberate
        # image-preview restriction rather than silently overriding it.
        if not any('max-image-preview' in directives for directives in page.robots):
            head += '<meta name="robots" content="max-image-preview:large">'
    def update_schema(match):
        try:
            value = json.loads(match.group(2))
        except ValueError:
            return match.group(0)  # The publication audit reports malformed data.
        def visit(node):
            if isinstance(node, list):
                for item in node:
                    visit(item)
            elif isinstance(node, dict):
                typ = node.get('@type', [])
                types = {typ} if isinstance(typ, str) else set(typ)
                if types & {'WebPage', 'CollectionPage'} and node.get('url') == page.canonical:
                    node['name'] = page.title.strip()
                    if page.description:
                        node['description'] = page.description
                    if page.image:
                        node['primaryImageOfPage'] = {'@type': 'ImageObject', 'url': image}
                if types & {'Article', 'BlogPosting', 'Report'} and page.image:
                    node.setdefault('image', image)
                if '@graph' in node:
                    visit(node['@graph'])
        visit(value)
        return match.group(1) + json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c') + match.group(3)
    head = LD.sub(update_schema, head)
    return head + tags + '</head>' + rest


def directory_page_path(page):
    return '/all-cars/' if page == 1 else f'/all-cars/page/{page}/'


def metadata_issues(text):
    """Cross-check the final head, including pages held outside search."""
    head = text.split('</head>', 1)[0]
    page = PageMetadata()
    page.feed(head)
    if not page.canonical or not page.title.strip():
        return []  # Error/redirect stubs are assessed by the route checks.
    issues = []
    for key, expected in [('og:title', page.title.strip()), ('og:url', page.canonical),
                          ('og:description', page.description), ('twitter:title', page.title.strip()),
                          ('twitter:description', page.description)]:
        if expected and page.metas.get(key) != expected:
            issues.append('Inconsistent ' + key)
    for match in LD.finditer(head):
        try:
            value = json.loads(match.group(2))
        except ValueError:
            issues.append('Malformed structured data')
            continue
        def check(node):
            if isinstance(node, list):
                for item in node:
                    check(item)
            elif isinstance(node, dict):
                typ = node.get('@type', [])
                types = {typ} if isinstance(typ, str) else set(typ)
                if (types & {'WebPage', 'CollectionPage'} and node.get('url') == page.canonical
                        and page.description and node.get('description') != page.description):
                    issues.append('Structured page description differs from meta description')
                if '@graph' in node:
                    check(node['@graph'])
        check(value)
    return issues


def directory_jumps(rows, size=120):
    """Direct HTML links to every directory range; no 133-click next-page chain."""
    links = []
    for offset in range(0, len(rows), size):
        page = offset // size + 1
        first, last = rows[offset]['n'], rows[min(offset + size, len(rows)) - 1]['n']
        label = f'{page}. {first} – {last}'
        links.append('<li><a href="' + directory_page_path(page) + '">'
                     + html.escape(label) + '</a></li>')
    return ('<details class="card directory-jumps"><summary>Jump to a name range</summary>'
            '<p>Choose any part of the A–Z directory.</p><ul>' + ''.join(links) + '</ul></details>')
