"""Central tag insertion: preview is unindexed and requests neither ads nor analytics."""
import json
import hashlib
import os
import re
from pathlib import Path
from publication_policy import ROOT, load_policy, ad_allowed, strip_ads

SCRIPT = re.compile(r'<script\b[^>]*>.*?</script>', re.I | re.S)


def strip_measurement(text):
    return SCRIPT.sub(lambda m: '' if any(token in m.group(0) for token in (
        'googletagmanager.com/gtag/', 'window.dataLayer', 'gtag("config"', "gtag('config'", 'data-analytics-id' )) else m.group(0), text)


def index_tags(text,url,policy,preview=False):
    if preview or (policy.get('index_policy') != 'preserve_template_gates' and url not in policy.get('index_pages', [])):
        text=re.sub(r'<meta\b[^>]*name=["\']robots["\'][^>]*>', '',text,flags=re.I)
        text=text.replace('</head>', '<meta name="robots" content="noindex,follow"></head>', 1)
    return text


def main():
    site=ROOT/'site'; policy=load_policy(); preview=os.environ.get('MOTORJURY_PREVIEW')=='1'
    client=os.environ.get('ADS_CLIENT','ca-pub-6675837012921030')
    ga=os.environ.get('GA4_ID','G-SD0YYNQ19N')
    privacy=(ROOT/'assets/privacy.mjs').read_text()
    privacy_name='privacy.'+hashlib.sha256(privacy.encode()).hexdigest()[:10]+'.mjs'
    (site/'assets'/privacy_name).write_text(privacy)
    privacy_css=(ROOT/'assets/privacy.css').read_text()
    privacy_style='privacy.'+hashlib.sha256(privacy_css.encode()).hexdigest()[:10]+'.css'
    (site/'assets'/privacy_style).write_text(privacy_css)
    consent="<script>window.mjAnalyticsAllowed=false;window.dataLayer=window.dataLayer||[];function gtag(){if(arguments[0]==='event'&&!window.mjAnalyticsAllowed)return;dataLayer.push(arguments)}gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied',functionality_storage:'granted',security_storage:'granted'});</script>"
    for f in site.rglob('*.html'):
        url='/'+f.relative_to(site).as_posix().removesuffix('index.html')
        text=strip_measurement(strip_ads(f.read_text())); tags=''
        text=index_tags(text,url,policy,preview)
        if preview:
            tags=''
        else:
            tags=f'<link rel="stylesheet" href="/assets/{privacy_style}">'+consent+f'<script type="module" src="/assets/{privacy_name}" data-analytics-id="{ga}"></script>'
            if ad_allowed(url,policy):
                tags+=f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={client}" crossorigin="anonymous"></script>'
        f.write_text(text.replace('</head>',tags+'</head>',1))
    (site/'ads.txt').write_text('google.com, '+client.replace('ca-pub-','pub-')+', DIRECT, f08c47fec0942fa0\n')
    print('TAGS: preview isolation' if preview else 'TAGS: analytics opt-in and explicit advertising eligibility')


if __name__=='__main__':main()
