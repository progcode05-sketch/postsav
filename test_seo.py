"""Offline tests for SEO and GEO: metadata, structured data, crawler files, headers, redirects and link integrity."""
import json
import os
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from PIL import Image

import app
import seo
import site_content as sc

ROOT = Path(__file__).parent
CONTENT_PATHS = list(sc.PAGES)
LEGAL_PATHS = list(sc.LEGAL)
ALL_PATHS = CONTENT_PATHS + LEGAL_PATHS
EXTERNAL_HOSTS = {'help.instagram.com', 'www.linkedin.com', 'help.pinterest.com', 'policy.pinterest.com', 'unsplash.com', 'github.com'}


def image_size(path):
    with Image.open(path) as image:
        return image.size


def soup_of(client, path, **kwargs):
    response = client.get(path, **kwargs)
    assert response.status_code == 200, (path, response.status_code)
    return BeautifulSoup(response.get_data(as_text=True), 'html.parser')


def graph(soup):
    blocks = soup.find_all('script', type='application/ld+json')
    assert len(blocks) == 1
    return json.loads(blocks[0].string)['@graph']


class Base(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        seo._page_cache.clear()


class MetadataTests(Base):
    def test_every_page_has_complete_unique_head_metadata(self):
        titles, descriptions = {}, {}
        for path in ALL_PATHS:
            soup = soup_of(self.client, path)
            title = soup.title.string.strip()
            description = soup.find('meta', attrs={'name': 'description'})['content']
            self.assertLessEqual(len(title), 60, f'{path} title is {len(title)} chars: {title}')
            self.assertGreaterEqual(len(title), 15, path)
            self.assertTrue(70 <= len(description) <= 160, f'{path} description is {len(description)} chars')
            self.assertNotIn(title, titles, f'{path} duplicates the title of {titles.get(title)}')
            self.assertNotIn(description, descriptions, f'{path} duplicates a description')
            titles[title], descriptions[description] = path, path
            self.assertEqual(soup.html['lang'], 'en', path)
            self.assertTrue(soup.find('meta', attrs={'name': 'viewport'}), path)
            self.assertEqual(len(soup.find_all('h1')), 1, f'{path} must have exactly one H1')

    def test_canonical_is_absolute_self_referencing_and_clean(self):
        for path in ALL_PATHS:
            soup = soup_of(self.client, path)
            canonical = soup.find('link', rel='canonical')['href']
            expected = 'http://localhost' + ('/' if path == '/' else path)
            self.assertEqual(canonical, expected, path)
            self.assertNotIn('?', canonical)
            self.assertEqual(soup.find('meta', property='og:url')['content'], canonical)
            robots = soup.find('meta', attrs={'name': 'robots'})['content']
            self.assertIn('index', robots)
            self.assertNotIn('noindex', robots)
            self.assertIn('max-snippet:-1', robots)

    def test_social_cards_are_complete(self):
        for path in ALL_PATHS:
            soup = soup_of(self.client, path)
            for prop in ('og:type', 'og:site_name', 'og:title', 'og:description', 'og:url', 'og:image', 'og:image:width', 'og:image:height', 'og:image:alt'):
                self.assertTrue(soup.find('meta', property=prop), f'{path} lacks {prop}')
            self.assertEqual(soup.find('meta', property='og:image')['content'], 'http://localhost/static/img/og-image.jpg')
            self.assertEqual(soup.find('meta', attrs={'name': 'twitter:card'})['content'], 'summary_large_image')
            self.assertEqual(soup.find('meta', property='og:title')['content'], soup.title.string.strip())

    def test_icons_manifest_and_stylesheet_are_linked(self):
        soup = soup_of(self.client, '/')
        rels = {tuple(link.get('rel')): link['href'] for link in soup.find_all('link')}
        self.assertIn(('icon',), rels)
        self.assertTrue(any(link['href'] == '/favicon.ico' for link in soup.find_all('link', rel='icon')))
        self.assertTrue(any(link['href'].endswith('.svg') for link in soup.find_all('link', rel='icon')))
        self.assertEqual(rels[('apple-touch-icon',)], '/static/icons/apple-touch-icon.png')
        self.assertEqual(rels[('manifest',)], '/site.webmanifest')
        self.assertRegex(rels[('stylesheet',)], r'^/static/site\.css\?v=[0-9a-f]{8}$')

    def test_heading_hierarchy_never_skips_a_level(self):
        for path in ALL_PATHS:
            soup = soup_of(self.client, path)
            levels = [int(h.name[1]) for h in soup.find_all(re.compile('^h[1-6]$'))]
            self.assertEqual(levels[0], 1, path)
            for before, after in zip(levels, levels[1:]):
                self.assertLessEqual(after, before + 1, f'{path} jumps from h{before} to h{after}')

    def test_content_pages_have_substantial_unique_text(self):
        minimum = {'/': 700, '/linkedin-downloader': 600, '/pinterest-downloader': 550, '/instagram-downloader': 500, '/about': 400}
        for path, words in minimum.items():
            soup = soup_of(self.client, path)
            main = soup.find('main')
            text = main.get_text(' ', strip=True)
            self.assertGreaterEqual(len(text.split()), words, f'{path} has too little text')

    def test_images_declare_alt_text_and_dimensions(self):
        for path in ALL_PATHS:
            for image in soup_of(self.client, path).find_all('img'):
                self.assertTrue(image.get('alt'), f'{path} image without alt: {image}')
                self.assertTrue(image.get('width') and image.get('height'), f'{path} image without size: {image}')

    def test_keyword_stuffing_is_avoided(self):
        # AI answer engines and Google both penalise repetition; keep any single content word modest.
        for path in CONTENT_PATHS:
            text = soup_of(self.client, path).find('main').get_text(' ', strip=True).lower()
            words = re.findall(r"[a-z']+", text)
            density = sum(1 for w in words if w.startswith('download')) / max(len(words), 1)
            self.assertLess(density, 0.05, f'{path} overuses "download" ({density:.1%})')


class StructuredDataTests(Base):
    def test_json_ld_is_valid_and_script_safe(self):
        for path in ALL_PATHS:
            raw = self.client.get(path).get_data(as_text=True)
            block = re.search(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S).group(1)
            self.assertNotIn('<', block, 'raw < inside JSON-LD could break out of the script tag')
            data = json.loads(block)
            self.assertEqual(data['@context'], 'https://schema.org')

    def test_core_entities_are_present_on_every_page(self):
        for path in ALL_PATHS:
            nodes = {node['@type']: node for node in graph(soup_of(self.client, path))}
            for kind in ('Organization', 'WebSite', 'WebApplication'):
                self.assertIn(kind, nodes, f'{path} lacks {kind}')
            org, application = nodes['Organization'], nodes['WebApplication']
            self.assertEqual(org['logo']['url'], 'http://localhost/static/icons/icon-512.png')
            self.assertEqual(application['offers'], {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'})
            self.assertTrue(application['isAccessibleForFree'])
            self.assertEqual(application['applicationCategory'], 'MultimediaApplication')

    def test_no_fabricated_ratings_or_reviews(self):
        for path in ALL_PATHS:
            raw = self.client.get(path).get_data(as_text=True)
            for forbidden in ('aggregateRating', '"Review"', 'ratingValue', 'reviewCount'):
                self.assertNotIn(forbidden, raw, f'{path} must not invent {forbidden}')

    def test_faq_schema_matches_visible_questions_and_answers(self):
        for path in CONTENT_PATHS:
            soup = soup_of(self.client, path)
            faq = next((n for n in graph(soup) if n['@type'] == 'FAQPage'), None)
            visible = [(d.summary.get_text(strip=True), d.p.get_text()) for d in soup.select('.faq details')]
            if path == '/about':
                self.assertIsNone(faq)
                continue
            self.assertIsNotNone(faq, path)
            declared = [(q['name'], q['acceptedAnswer']['text']) for q in faq['mainEntity']]
            self.assertEqual(len(declared), len(visible), path)
            for (dq, da), (vq, va) in zip(declared, visible):
                self.assertEqual(dq, vq, path)
                self.assertEqual(re.sub(r'\s+', ' ', da), re.sub(r'\s+', ' ', va), f'{path}: FAQ answer differs from the visible text')

    def test_howto_schema_matches_visible_steps(self):
        for path in CONTENT_PATHS:
            soup = soup_of(self.client, path)
            if path == '/about':  # describes the tool's internals, not a task for the reader, so no HowTo markup
                self.assertFalse([n for n in graph(soup) if n['@type'] == 'HowTo'])
                continue
            howto = next(n for n in graph(soup) if n['@type'] == 'HowTo')
            visible = [step.h3.get_text(strip=True) for step in soup.select('.steps .step')]
            self.assertEqual([s['name'] for s in howto['step']], visible, path)
            self.assertEqual([s['position'] for s in howto['step']], list(range(1, len(visible) + 1)))
            self.assertTrue(all(s['text'] and s['url'].startswith('http://localhost/') for s in howto['step']))

    def test_breadcrumbs_match_visible_trail_and_use_absolute_urls(self):
        for path in CONTENT_PATHS[1:] + LEGAL_PATHS:
            soup = soup_of(self.client, path)
            crumbs = next(n for n in graph(soup) if n['@type'] == 'BreadcrumbList')['itemListElement']
            self.assertEqual(crumbs[0]['item'], 'http://localhost/')
            self.assertEqual(crumbs[-1]['item'], 'http://localhost' + path)
            self.assertEqual([c['position'] for c in crumbs], [1, 2])
            visible = soup.select_one('.crumbs').get_text('|', strip=True).replace('|/|', '|')
            self.assertEqual(visible.split('|'), [c['name'] for c in crumbs])
        self.assertFalse([n for n in graph(soup_of(self.client, '/')) if n['@type'] == 'BreadcrumbList'])

    def test_webpage_nodes_declare_dates_and_primary_image(self):
        for path in ALL_PATHS:
            page = next(n for n in graph(soup_of(self.client, path)) if n['@type'] in ('WebPage', 'AboutPage', 'ContactPage'))
            self.assertRegex(page['dateModified'], r'^\d{4}-\d{2}-\d{2}$')
            self.assertEqual(page['primaryImageOfPage']['url'], 'http://localhost/static/img/og-image.jpg')
        self.assertEqual(next(n for n in graph(soup_of(self.client, '/about')) if n['@type'] == 'AboutPage')['url'], 'http://localhost/about')
        self.assertEqual(next(n for n in graph(soup_of(self.client, '/contact')) if n['@type'] == 'ContactPage')['url'], 'http://localhost/contact')

    def test_contact_email_is_published_in_the_organization_only_when_configured(self):
        with patch.dict(os.environ, {'CONTACT_EMAIL': 'hello@example.test'}):
            org = next(n for n in graph(soup_of(self.client, '/')) if n['@type'] == 'Organization')
        self.assertEqual(org['email'], 'hello@example.test')
        with patch.dict(os.environ, {'CONTACT_EMAIL': ''}):
            seo._page_cache.clear()
            org = next(n for n in graph(soup_of(self.client, '/')) if n['@type'] == 'Organization')
        self.assertNotIn('email', org)


class CrawlerFileTests(Base):
    def test_robots_txt_welcomes_search_and_ai_crawlers_and_hides_the_api(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith('text/plain'))
        text = response.get_data(as_text=True)
        self.assertIn('Sitemap: http://localhost/sitemap.xml', text)
        groups = [g for g in re.split(r'\n\s*\n', text) if 'User-agent:' in g]
        self.assertGreaterEqual(len(groups), 2)
        for group in groups:
            self.assertIn('Allow: /', group)
            for private in ('/api/', '/healthz', '/readyz'):
                self.assertIn(f'Disallow: {private}', group, 'every group must repeat the private paths')
        agents = set(re.findall(r'User-agent: (\S+)', text))
        for bot in ('*', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'PerplexityBot', 'Google-Extended', 'Bingbot', 'Googlebot'):
            self.assertIn(bot, agents)
        self.assertNotRegex(text, r'(?m)^Disallow:\s*/\s*$', 'must never disallow the whole site')

    def test_sitemap_lists_every_indexable_page_once_with_valid_dates(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith('application/xml'))
        tree = ET.fromstring(response.data)
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [(u.find('s:loc', ns).text, u.find('s:lastmod', ns).text) for u in tree.findall('s:url', ns)]
        self.assertEqual(sorted(loc for loc, _ in urls), sorted('http://localhost' + ('/' if p == '/' else p) for p in ALL_PATHS))
        self.assertEqual(len({loc for loc, _ in urls}), len(urls))
        for loc, lastmod in urls:
            datetime.strptime(lastmod, '%Y-%m-%d')
            self.assertEqual(self.client.get(loc.replace('http://localhost', '')).status_code, 200, loc)
        for forbidden in ('/api/', 'healthz', 'readyz', '/static/', '404'):
            self.assertFalse([loc for loc, _ in urls if forbidden in loc])

    def test_llms_txt_follows_the_convention_and_links_to_real_pages(self):
        response = self.client.get('/llms.txt')
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        lines = text.split('\n')
        self.assertEqual(lines[0], '# PostSav')
        self.assertTrue(lines[2].startswith('> '), 'summary blockquote required')
        self.assertIn('not affiliated', text)
        for heading in ('## Key facts', '## Downloaders', '## About and policies', '## Optional'):
            self.assertIn(heading, text)
        for label, url in re.findall(r'\[([^\]]+)\]\((http[^)]+)\)', text):
            self.assertTrue(url.startswith('http://localhost') or url == sc.GITHUB_URL, url)
            if url.startswith('http://localhost'):
                self.assertEqual(self.client.get(url.replace('http://localhost', '')).status_code, 200, url)

    def test_llms_full_contains_every_page_with_its_faq_and_absolute_links(self):
        text = self.client.get('/llms-full.txt').get_data(as_text=True)
        for path in ('/', '/linkedin-downloader', '/pinterest-downloader', '/instagram-downloader', '/about'):
            page = sc.PAGES[path]
            self.assertIn(f'# {page["title"]}', text)
            for section in page['sections']:
                if section['type'] == 'faq':
                    for question, _answer in section['items']:
                        self.assertIn(f'### {question}', text)
        self.assertNotRegex(text, r'\]\(/', 'relative links are useless outside the site')
        self.assertIn('| Platform | Images | Videos |', text)

    def test_pricing_markdown_states_free_and_the_real_limits(self):
        response = self.client.get('/pricing.md')
        self.assertTrue(response.content_type.startswith('text/markdown'))
        text = response.get_data(as_text=True)
        self.assertIn('Price: $0', text)
        self.assertIn('250 MB per file', text)
        self.assertIn('500 MB per ZIP', text)

    def test_security_txt_requires_a_contact_and_expires_in_the_future(self):
        with patch.dict(os.environ, {'CONTACT_EMAIL': ''}):
            self.assertEqual(self.client.get('/.well-known/security.txt').status_code, 404)
        with patch.dict(os.environ, {'CONTACT_EMAIL': 'sec@example.test'}):
            text = self.client.get('/.well-known/security.txt').get_data(as_text=True)
        self.assertIn('Contact: mailto:sec@example.test', text)
        expires = datetime.strptime(re.search(r'Expires: (\S+)', text).group(1), '%Y-%m-%dT%H:%M:%S.000Z').replace(tzinfo=timezone.utc)
        self.assertGreater(expires, datetime.now(timezone.utc))
        self.assertIn('Canonical: http://localhost/.well-known/security.txt', text)

    def test_indexnow_key_file_serves_exactly_the_key(self):
        response = self.client.get(f'/{seo.INDEXNOW_KEY}.txt')
        self.assertEqual((response.status_code, response.get_data(as_text=True)), (200, seo.INDEXNOW_KEY))
        self.assertRegex(seo.INDEXNOW_KEY, r'^[A-Za-z0-9-]{8,128}$')

    def test_manifest_icons_and_social_image_exist_with_the_right_sizes(self):
        manifest = self.client.get('/site.webmanifest').get_json(force=True)
        self.assertEqual(manifest['name'], 'PostSav')
        for icon in manifest['icons']:
            size = int(icon['sizes'].split('x')[0])
            self.assertEqual(image_size(ROOT / icon['src'].lstrip('/')), (size, size))
        favicon = self.client.get('/favicon.ico')
        self.assertEqual((favicon.status_code, favicon.mimetype), (200, 'image/x-icon'))
        favicon.close()
        with Image.open(ROOT / 'static/icons/favicon.ico') as ico:
            self.assertGreaterEqual(max(ico.info['sizes'])[0], 48)
        self.assertEqual(image_size(ROOT / 'static/icons/apple-touch-icon.png'), (180, 180))
        og = ROOT / 'static/img/og-image.jpg'
        self.assertEqual(image_size(og), (1200, 630))
        self.assertLess(og.stat().st_size, 200 * 1024)


class HeaderAndRedirectTests(Base):
    def test_operational_endpoints_are_noindex_and_uncached(self):
        for path in ('/healthz', '/readyz'):
            headers = self.client.get(path).headers
            self.assertEqual(headers['X-Robots-Tag'], 'noindex, nofollow', path)
            self.assertEqual(headers['Cache-Control'], 'no-store', path)
        missing = self.client.get('/api/nothing-here')
        self.assertEqual((missing.status_code, missing.get_json()), (404, {'error': 'Not found.'}))
        self.assertEqual(missing.headers['X-Robots-Tag'], 'noindex, nofollow')

    def test_html_pages_are_cacheable_and_support_conditional_requests(self):
        for path in ('/', '/linkedin-downloader', '/terms'):
            first = self.client.get(path)
            self.assertRegex(first.headers['Cache-Control'], r'^public, max-age=\d+$')
            self.assertNotIn('X-Robots-Tag', first.headers)
            etag = first.headers['ETag']
            second = self.client.get(path, headers={'If-None-Match': etag})
            self.assertEqual(second.status_code, 304, path)
            self.assertEqual(self.client.get(path, headers={'If-None-Match': '"other"'}).status_code, 200)
        self.assertEqual(self.client.head('/').status_code, 200)

    def test_referrer_policy_is_origin_only_for_pages_and_none_for_the_api(self):
        self.assertEqual(self.client.get('/').headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertEqual(self.client.get('/healthz').headers['Referrer-Policy'], 'no-referrer')

    def test_trailing_slashes_redirect_permanently_with_the_query_preserved(self):
        for path in ('/linkedin-downloader/', '/about/', '/terms/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 301, path)
            self.assertEqual(response.headers['Location'], 'http://localhost' + path.rstrip('/'))
        self.assertEqual(self.client.get('/about/?x=1').headers['Location'], 'http://localhost/about?x=1')
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_secondary_hosts_redirect_to_the_canonical_site_but_health_checks_do_not(self):
        with patch.dict(os.environ, {'SITE_URL': 'https://www.postsav.example'}):
            moved = self.client.get('/about', base_url='https://social-downloader.onrender.com')
            self.assertEqual(moved.status_code, 301)
            self.assertEqual(moved.headers['Location'], 'https://www.postsav.example/about')
            self.assertEqual(self.client.get('/healthz', base_url='https://social-downloader.onrender.com').status_code, 200)
            self.assertEqual(self.client.get('/about', base_url='https://www.postsav.example').status_code, 200)
            self.assertEqual(self.client.post('/api/info', json={}, base_url='https://social-downloader.onrender.com').status_code, 400)

    def test_unknown_pages_return_a_helpful_noindex_404(self):
        response = self.client.get('/definitely-not-a-page')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers['X-Robots-Tag'], 'noindex')
        soup = BeautifulSoup(response.get_data(as_text=True), 'html.parser')
        self.assertIn('noindex', soup.find('meta', attrs={'name': 'robots'})['content'])
        self.assertFalse(soup.find('link', rel='canonical'))
        self.assertGreaterEqual(len(soup.select('a.pcard')), 3)


class CanonicalBaseTests(Base):
    def test_site_url_beats_render_url_beats_the_request(self):
        def canonical(**kwargs):
            seo._page_cache.clear()
            return soup_of(self.client, '/about', **kwargs).find('link', rel='canonical')['href']
        with patch.dict(os.environ, {'RENDER_EXTERNAL_URL': 'https://service.onrender.com', 'SITE_URL': ''}):
            self.assertEqual(canonical(), 'https://service.onrender.com/about')
        with patch.dict(os.environ, {'RENDER_EXTERNAL_URL': 'https://service.onrender.com', 'SITE_URL': 'https://postsav.example/'}):
            self.assertEqual(canonical(base_url='https://postsav.example'), 'https://postsav.example/about')
        with patch.dict(os.environ, {'RENDER_EXTERNAL_URL': '', 'SITE_URL': 'not-a-url'}):
            self.assertEqual(canonical(), 'http://localhost/about')

    def test_fallback_origin_is_https_for_public_hosts_and_ignores_hostile_host_headers(self):
        with patch.dict(os.environ, {'SITE_URL': '', 'RENDER_EXTERNAL_URL': ''}):
            seo._page_cache.clear()
            self.assertEqual(soup_of(self.client, '/about', base_url='http://postsav.example').find('link', rel='canonical')['href'], 'https://postsav.example/about')
            self.assertEqual(soup_of(self.client, '/about', base_url='http://127.0.0.1:5055').find('link', rel='canonical')['href'], 'http://127.0.0.1:5055/about')
            for hostile in ('evil.test"><script>alert(1)</script>', 'a b', 'x.test/../y'):
                seo._page_cache.clear()
                response = self.client.get('/robots.txt', headers={'Host': hostile})
                self.assertNotIn('script', response.get_data(as_text=True))
                self.assertIn('Sitemap: http://localhost/sitemap.xml', response.get_data(as_text=True))

    def test_everything_generated_uses_the_configured_origin(self):
        with patch.dict(os.environ, {'SITE_URL': 'https://postsav.example'}):
            seo._page_cache.clear()
            client = app.app.test_client()
            headers = dict(base_url='https://postsav.example')
            for path in ('/robots.txt', '/sitemap.xml', '/llms.txt', '/llms-full.txt', '/pricing.md'):
                text = client.get(path, **headers).get_data(as_text=True)
                self.assertIn('https://postsav.example', text, path)
                self.assertNotIn('localhost', text, path)
            ld = client.get('/', **headers).get_data(as_text=True)
            self.assertNotIn('localhost', ld)

    def test_search_console_verification_tags_are_opt_in(self):
        soup = soup_of(self.client, '/')
        self.assertFalse(soup.find('meta', attrs={'name': 'google-site-verification'}))
        with patch.dict(os.environ, {'GOOGLE_SITE_VERIFICATION': 'abc123', 'BING_SITE_VERIFICATION': 'def456'}):
            soup = soup_of(self.client, '/about')
        self.assertEqual(soup.find('meta', attrs={'name': 'google-site-verification'})['content'], 'abc123')
        self.assertEqual(soup.find('meta', attrs={'name': 'msvalidate.01'})['content'], 'def456')

    def test_brand_name_can_be_changed_with_one_setting(self):
        code = ("import app; c = app.app.test_client(); h = c.get('/').get_data(as_text=True); "
                "print('Acme Saver' in h, 'PostSav' in h, 'Acme Saver' in c.get('/llms.txt').get_data(as_text=True))")
        env = {**os.environ, 'SITE_NAME': 'Acme Saver'}
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ['True', 'False', 'True'])


class LinkIntegrityTests(Base):
    def test_every_internal_link_and_anchor_resolves(self):
        known = set(ALL_PATHS) | {'/robots.txt', '/sitemap.xml', '/llms.txt', '/llms-full.txt', '/pricing.md', '/favicon.ico', '/site.webmanifest'}
        for path in ALL_PATHS:
            soup = soup_of(self.client, path)
            ids = {tag['id'] for tag in soup.find_all(id=True)}
            for anchor in soup.find_all('a', href=True):
                href = anchor['href']
                self.assertTrue(anchor.get_text(strip=True) or anchor.get('aria-label'), f'{path}: empty link text for {href}')
                self.assertNotIn(anchor.get_text(strip=True).lower(), ('click here', 'here', 'read more'), f'{path}: non-descriptive link text')
                if href.startswith('#'):
                    self.assertIn(href[1:], ids, f'{path}: broken anchor {href}')
                elif href.startswith('/'):
                    target, _, fragment = href.partition('#')
                    target = target or '/'
                    self.assertIn(target, known, f'{path}: unknown internal link {href}')
                    if fragment and target != '/':
                        self.assertIn(fragment, {tag['id'] for tag in soup_of(self.client, target).find_all(id=True)}, f'{path}: {href}')
                    if fragment and target == '/':
                        self.assertIn(fragment, {tag['id'] for tag in soup_of(self.client, '/').find_all(id=True)} | {'tool'}, f'{path}: {href}')

    def test_external_links_use_https_noopener_and_trusted_hosts(self):
        for path in ALL_PATHS:
            for anchor in soup_of(self.client, path).find_all('a', href=re.compile('^https?://')):
                href = anchor['href']
                self.assertTrue(href.startswith('https://'), f'{path}: insecure link {href}')
                host = href.split('/')[2]
                self.assertIn(host, EXTERNAL_HOSTS, f'{path}: unexpected external host {host}')
                self.assertIn('noopener', anchor.get('rel', []), f'{path}: {href} needs rel=noopener')

    def test_internal_navigation_reaches_every_page_from_the_home_page(self):
        reachable = {a['href'].split('#')[0] or '/' for a in soup_of(self.client, '/').find_all('a', href=True) if a['href'].startswith('/')}
        for path in ALL_PATHS:
            self.assertIn(path, reachable, f'{path} is an orphan page (not linked from the home page)')

    def test_platform_pages_cross_link_to_each_other(self):
        for path in ('/linkedin-downloader', '/pinterest-downloader', '/instagram-downloader'):
            hrefs = {a['href'] for a in soup_of(self.client, path).select('.pcard')}
            self.assertEqual(len(hrefs), 2, path)
            self.assertNotIn(path, hrefs)


class ContentIntegrityTests(Base):
    def test_published_limits_match_the_application(self):
        code = ("import app, site_content as sc; print(app.MAX_FILE // 1048576, app.MAX_BUNDLE // 1048576, app.SESSION_TTL // 60, "
                "app.RATE_INFO_PER_MIN, app.RATE_DOWNLOAD_PER_MIN)")
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env={**os.environ, 'PUBLIC_MODE': '1'}, capture_output=True, text=True).stdout.split()
        limits = sc.LIMITS
        self.assertEqual([int(v) for v in out], [limits['file_mb'], limits['zip_mb'], limits['session_minutes'], limits['lookups_per_min'], limits['downloads_per_min']])
        self.assertIn('len(post[\'assets\']) > %d' % limits['attachments'], (ROOT / 'app.py').read_text(encoding='utf-8'))

    def test_pages_state_dates_that_match_the_content_model(self):
        for path in CONTENT_PATHS:
            soup = soup_of(self.client, path)
            updated = soup.select_one('.updated')
            self.assertIn(seo.display_date(sc.UPDATED), updated.get_text(), path)
            self.assertEqual(updated.find('time')['datetime'], sc.UPDATED)

    def test_every_claimed_tested_link_count_adds_up(self):
        # 17 = 7 LinkedIn + 4 Instagram + 6 Pinterest, the cases in verify_live.py that were run on 2 October 2026.
        source = (ROOT / 'verify_live.py').read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r"^    \('LinkedIn", source, re.M)), 7)
        self.assertEqual(len(re.findall(r"^    \('Instagram", source, re.M)), 4)
        self.assertEqual(len(re.findall(r"^    \('Pinterest", source, re.M)), 6)
        facts = next(s for s in sc.PAGES['/']['sections'] if s['id'] == 'at-a-glance')
        self.assertIn('17 of 17', dict(facts['items'])['Last tested'])

    def test_inline_markup_is_escaped_and_only_safe_links_become_anchors(self):
        rendered = str(seo.md_inline('<script>alert(1)</script> **b** `c` [ok](/terms) [ext](https://example.test/a?b=1&c=2) [bad](javascript:alert(1))'))
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('<strong>b</strong>', rendered)
        self.assertIn('<a href="/terms">ok</a>', rendered)
        self.assertIn('<a href="https://example.test/a?b=1&amp;c=2" rel="noopener">ext</a>', rendered)
        self.assertNotIn('href="javascript', rendered)
        self.assertEqual(seo.md_plain('[a](/x) **b** `c`'), 'a b c')
        self.assertEqual(seo.md_absolute('[a](/x) [b](https://y.test)', 'https://s.test'), '[a](https://s.test/x) [b](https://y.test)')

    def test_deployment_files_ship_the_new_modules_and_assets(self):
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        for token in ('seo.py', 'site_content.py', 'COPY static ./static', 'COPY templates ./templates'):
            self.assertIn(token, dockerfile)


if __name__ == '__main__':
    unittest.main()
