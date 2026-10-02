"""Opt-in SEO/GEO check of a deployed site: crawler files, per-page metadata, structured data and links.

Usage: python verify_seo.py https://your-site.example [--external]
--external also requests every outbound link (official help pages, terms). Sites that refuse automated requests
(401/403/429, or Instagram's help center answering 400) are reported as WARN, not as broken links.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
AI_BOTS = ('GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'PerplexityBot', 'Google-Extended', 'Bingbot')


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, ok, message):
        print(('  PASS  ' if ok else '  FAIL  ') + message)
        self.failures += 0 if ok else 1
        return ok


def get(url, **kwargs):
    return requests.get(url, headers=UA, timeout=60, **kwargs)


def check_site(site, external=False):
    site = site.rstrip('/')
    report = Report()
    print(f'== crawler files on {site}')
    robots = get(f'{site}/robots.txt')
    report.check(robots.status_code == 200 and robots.headers.get('content-type', '').startswith('text/plain'), f'robots.txt -> {robots.status_code} {robots.headers.get("content-type")}')
    report.check(f'Sitemap: {site}/sitemap.xml' in robots.text, 'robots.txt links the sitemap with an absolute URL')
    report.check(not re.search(r'(?m)^Disallow:\s*/\s*$', robots.text), 'robots.txt does not disallow the whole site (Render serves disallow-all while a free service sleeps)')
    report.check(all(f'User-agent: {bot}' in robots.text for bot in AI_BOTS), 'robots.txt names the main search and AI crawlers')
    sitemap = get(f'{site}/sitemap.xml')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = [u.find('s:loc', ns).text for u in ET.fromstring(sitemap.content).findall('s:url', ns)] if sitemap.status_code == 200 else []
    report.check(bool(urls) and all(u.startswith(site) for u in urls), f'sitemap.xml lists {len(urls)} URLs on this origin')
    for name in ('llms.txt', 'llms-full.txt', 'pricing.md', 'site.webmanifest', 'favicon.ico', 'static/img/og-image.jpg', 'static/icons/icon-512.png'):
        response = get(f'{site}/{name}')
        report.check(response.status_code == 200, f'{name} -> {response.status_code} {response.headers.get("content-type", "")} ({len(response.content)} bytes)')
    for path in ('/healthz', '/readyz'):
        response = get(site + path)
        report.check('noindex' in response.headers.get('x-robots-tag', ''), f'{path} sends X-Robots-Tag: noindex')
    missing = get(f'{site}/definitely-missing-page')
    report.check(missing.status_code == 404 and 'noindex' in missing.headers.get('x-robots-tag', ''), 'unknown URLs return a noindex 404')
    slash = get(f'{site}/about/', allow_redirects=False)
    report.check(slash.status_code == 301 and slash.headers.get('location', '').rstrip('/').endswith('/about') and not slash.headers['location'].endswith('/'), 'trailing-slash URLs 301 to the clean URL')

    print('== pages')
    titles, links = {}, set()
    for url in urls:
        response = get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else ''
        description = (soup.find('meta', attrs={'name': 'description'}) or {}).get('content', '')
        canonical = (soup.find('link', rel='canonical') or {}).get('href', '')
        ld_blocks = soup.find_all('script', type='application/ld+json')
        try:
            types = sorted({node['@type'] for block in ld_blocks for node in json.loads(block.string)['@graph']})
        except (ValueError, KeyError, TypeError):
            types = []
        print(f' {url}')
        report.check(response.status_code == 200, f'status {response.status_code}, {len(response.content) // 1024} KB, encoding {response.headers.get("content-encoding", "none")}')
        report.check(0 < len(title) <= 60 and title not in titles, f'title ({len(title)} chars, unique): {title}')
        titles[title] = url
        report.check(70 <= len(description) <= 160, f'meta description {len(description)} chars')
        report.check(canonical == url, f'canonical is self-referencing ({canonical})')
        report.check(len(soup.find_all('h1')) == 1, 'exactly one H1')
        report.check({'Organization', 'WebSite', 'WebApplication', 'WebPage'} <= set(types) | {'WebPage', 'AboutPage', 'ContactPage'}, f'JSON-LD types: {", ".join(types)}')
        report.check(bool(soup.find('meta', property='og:image')) and bool(soup.find('meta', attrs={'name': 'twitter:card'})), 'Open Graph and Twitter card tags present')
        for anchor in soup.find_all('a', href=True):
            if anchor['href'].startswith('https://') and not anchor['href'].startswith(site):
                links.add(anchor['href'])
    if external:
        print('== outbound links')
        for link in sorted(links):
            response = requests.get(link, headers=UA, timeout=60)
            status = response.status_code
            blocks_bots = status in (401, 403, 429, 999) or (status == 400 and 'instagram.com' in link)
            if blocks_bots:
                print(f'  WARN  {status} {link} (the site refuses automated requests; open it in a browser to confirm it works)')
            else:
                report.check(status < 400, f'{status} {link}')
    print(f'\n{"ALL CHECKS PASSED" if not report.failures else str(report.failures) + " CHECK(S) FAILED"}')
    return report.failures


if __name__ == '__main__':
    if len(sys.argv) < 2 or not sys.argv[1].startswith('http'):
        print(__doc__)
        sys.exit(2)
    sys.exit(1 if check_site(sys.argv[1], '--external' in sys.argv) else 0)
