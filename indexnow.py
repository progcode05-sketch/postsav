"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver) that pages were added or changed.

Bing's index also feeds Microsoft Copilot and ChatGPT search, so fast Bing indexing helps AI visibility.
Google does not use IndexNow; submit the sitemap in Google Search Console instead.

Usage:
    python indexnow.py https://your-site.example            # submit every URL in the sitemap
    python indexnow.py https://your-site.example /about     # submit specific paths

Run it after a deploy, and only for a site you own: the key file at /<key>.txt must be reachable first.
"""
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import seo

ENDPOINT = 'https://api.indexnow.org/indexnow'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (indexnow submitter)'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read().decode('utf-8', 'replace')


def sitemap_urls(site):
    _status, body = fetch(f'{site}/sitemap.xml')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [loc.text.strip() for loc in ET.fromstring(body).findall('.//s:loc', ns)]


def main(argv):
    if len(argv) < 2 or not argv[1].startswith('https://'):
        print(__doc__)
        return 2
    site = argv[1].rstrip('/')
    key = seo.INDEXNOW_KEY
    status, served = fetch(f'{site}/{key}.txt')
    if status != 200 or served.strip() != key:
        print(f'The key file {site}/{key}.txt is not live yet (status {status}). Deploy first.')
        return 1
    urls = [site + path if path.startswith('/') else path for path in argv[2:]] or sitemap_urls(site)
    payload = {'host': urlsplit(site).netloc, 'key': key, 'keyLocation': f'{site}/{key}.txt', 'urlList': urls}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode('utf-8'), method='POST',
                                     headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f'IndexNow accepted {len(urls)} URLs (HTTP {response.status}).')
    except urllib.error.HTTPError as error:
        print(f'IndexNow refused the submission: HTTP {error.code} {error.reason}')
        return 1
    for url in urls:
        print('  ', url)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
