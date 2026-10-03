"""SEO and GEO plumbing: canonical URLs, structured data, crawler files and AI-friendly summaries.

Pages and copy live in site_content.py; this module turns them into HTML context, JSON-LD, robots.txt, sitemap.xml,
llms.txt, llms-full.txt, pricing.md, security.txt and the IndexNow key file.
"""
import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit

from flask import Response, jsonify, redirect, render_template, request, send_from_directory
from markupsafe import Markup

import site_content as sc

# IndexNow (Bing, Yandex and others) verifies ownership by fetching /<key>.txt. The key is public by design.
INDEXNOW_KEY = os.environ.get('INDEXNOW_KEY', '').strip() or '8e7d436cc52aa0e1ed02c4945b107f39'
HEALTH_PATHS = ('/healthz', '/readyz')
OG_IMAGE_PATH = '/static/img/og-image.jpg'
LOGO_PATH = '/static/icons/icon-512.png'

# Crawlers that power search and AI assistants. Listing them is explicit documentation: they are welcome.
CRAWLERS = [
    'GPTBot', 'OAI-SearchBot', 'ChatGPT-User',            # OpenAI (ChatGPT search and browsing)
    'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'anthropic-ai',  # Anthropic (Claude)
    'PerplexityBot', 'Perplexity-User',                    # Perplexity
    'Googlebot', 'Google-Extended',                        # Google Search, AI Overviews and Gemini
    'Bingbot',                                             # Bing, which feeds Microsoft Copilot and ChatGPT search
    'Applebot', 'Applebot-Extended',                       # Apple
    'DuckDuckBot', 'DuckAssistBot',                        # DuckDuckGo
    'MistralAI-User', 'Amazonbot', 'Meta-ExternalAgent', 'CCBot',
]
PRIVATE_PATHS = ('/api/', '/healthz', '/readyz')

_page_cache = {}
_asset_versions = {}
_LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')


# ---------------------------------------------------------------------------------------------------- text helpers
def md_inline(text):
    """Render the small inline markup used in site_content (links, bold, code) as safe HTML."""
    out = html.escape(text, quote=False)

    def link(match):
        label, url = match.group(1), html.unescape(match.group(2))
        if not re.match(r'(https://|/|#)', url):
            return match.group(0)
        rel = ' rel="noopener"' if url.startswith('https://') else ''
        return f'<a href="{html.escape(url, quote=True)}"{rel}>{label}</a>'

    out = _LINK.sub(link, out)
    out = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', out)
    out = re.sub(r'`([^`]+)`', r'<code>\1</code>', out)
    return Markup(out)


def md_plain(text):
    text = _LINK.sub(lambda m: m.group(1), text)
    return re.sub(r'[*`]', '', text)


def md_absolute(text, base):
    """Markdown links with site-relative targets become absolute (for llms-full.txt)."""
    return _LINK.sub(lambda m: f'[{m.group(1)}]({base + m.group(2) if m.group(2).startswith("/") else m.group(2)})', text)


def display_date(iso):
    d = datetime.strptime(iso, '%Y-%m-%d')
    return f'{d.day} {d.strftime("%B %Y")}'


# ---------------------------------------------------------------------------------------------------- urls
def base_url():
    """Public origin used in canonical tags, sitemap and structured data."""
    explicit = os.environ.get('SITE_URL', '').strip().rstrip('/')
    if explicit.startswith(('https://', 'http://')):
        return explicit
    external = os.environ.get('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
    if external.startswith('https://'):
        return external
    return origin_from_request()


_LOCAL_HOSTS = ('localhost', '127.0.0.1', '[::1]')
_SAFE_HOST = re.compile(r'[A-Za-z0-9.-]+(:\d{1,5})?')


def origin_from_request():
    """Fallback origin from the request. The Host header is untrusted input, so only plain hostnames are used,
    and any non-local host is assumed to be served over https (proxies often hide the real scheme)."""
    host = request.host
    if not _SAFE_HOST.fullmatch(host):
        return 'http://localhost'
    name = host.split(':')[0].lower()
    local = name in _LOCAL_HOSTS or name.endswith(('.local', '.localhost', '.test'))
    return ('http://' if local else 'https://') + host


def page_url(base, path):
    return base + ('/' if path == '/' else path)


def asset(name):
    """Static file URL with a content hash, so long-lived caching never serves stale CSS or JS."""
    version = _asset_versions.get(name)
    if version is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', name), 'rb') as handle:
                version = hashlib.md5(handle.read()).hexdigest()[:8]
        except OSError:
            version = '0'
        _asset_versions[name] = version
    return f'/static/{name}?v={version}'


def contact_email():
    return os.environ.get('CONTACT_EMAIL', '').strip()


def site_info(base):
    return dict(name=sc.BRAND, tagline=sc.TAGLINE, url=base, email=contact_email(), github=sc.GITHUB_URL,
                updated=display_date(sc.UPDATED), tested=sc.TESTED_ON, nav=sc.NAV, footer_groups=sc.FOOTER_GROUPS,
                google_verification=os.environ.get('GOOGLE_SITE_VERIFICATION', '').strip(),
                bing_verification=os.environ.get('BING_SITE_VERIFICATION', '').strip())


# ---------------------------------------------------------------------------------------------------- structured data
def jsonld(page, base):
    """schema.org graph for a page, generated from the same data that renders the visible content."""
    url = page_url(base, page['path'])
    org, site, app = f'{base}/#organization', f'{base}/#website', f'{base}/#app'
    home = sc.PAGES['/']
    organization = {'@type': 'Organization', '@id': org, 'name': sc.BRAND, 'url': base + '/', 'sameAs': [sc.GITHUB_URL],
                    'logo': {'@type': 'ImageObject', '@id': f'{base}/#logo', 'url': base + LOGO_PATH, 'width': 512, 'height': 512}}
    if contact_email():
        organization['email'] = contact_email()
    nodes = [
        organization,
        {'@type': 'WebSite', '@id': site, 'url': base + '/', 'name': sc.BRAND, 'description': home['description'], 'inLanguage': 'en', 'publisher': {'@id': org}},
        {'@type': 'WebApplication', '@id': app, 'name': sc.BRAND, 'url': base + '/', 'description': md_plain(home['lead']),
         'applicationCategory': 'MultimediaApplication', 'operatingSystem': 'Any', 'browserRequirements': 'Requires JavaScript and a modern web browser.',
         'isAccessibleForFree': True, 'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}, 'featureList': sc.FEATURE_LIST,
         'screenshot': base + OG_IMAGE_PATH, 'inLanguage': 'en', 'publisher': {'@id': org}},
    ]
    kind = page.get('kind')
    webpage = {'@type': {'about': 'AboutPage'}.get(kind, 'ContactPage' if page['path'] == '/contact' else 'WebPage'), '@id': url + '#webpage', 'url': url,
               'name': page['title'], 'description': page['description'], 'isPartOf': {'@id': site}, 'about': {'@id': app}, 'inLanguage': 'en',
               'dateModified': page['updated'], 'primaryImageOfPage': {'@type': 'ImageObject', 'url': base + OG_IMAGE_PATH, 'width': 1200, 'height': 630}}
    crumbs = page.get('breadcrumb') or []
    if crumbs:
        webpage['breadcrumb'] = {'@id': url + '#breadcrumb'}
    nodes.append(webpage)
    if crumbs:
        nodes.append({'@type': 'BreadcrumbList', '@id': url + '#breadcrumb', 'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'name': name, 'item': page_url(base, path)} for i, (name, path) in enumerate(crumbs, 1)]})
    for section in page.get('sections', []):
        if section['type'] == 'faq':
            nodes.append({'@type': 'FAQPage', '@id': url + '#faq', 'mainEntityOfPage': {'@id': url + '#webpage'}, 'mainEntity': [
                {'@type': 'Question', 'name': md_plain(q), 'acceptedAnswer': {'@type': 'Answer', 'text': md_plain(a)}} for q, a in section['items']]})
        if section['type'] == 'steps' and section.get('howto_name'):
            nodes.append({'@type': 'HowTo', '@id': url + '#howto', 'name': section['howto_name'], 'description': md_plain(section.get('intro', '')),
                          'step': [{'@type': 'HowToStep', 'position': i, 'name': name, 'text': md_plain(text), 'url': f'{url}#{section["id"]}'}
                                   for i, (name, text) in enumerate(section['items'], 1)]})
    payload = json.dumps({'@context': 'https://schema.org', '@graph': nodes}, ensure_ascii=False, separators=(',', ':'))
    return payload.replace('<', '\\u003c')


def page_meta(page, base=None, noindex=False):
    """Template context shared by every page that extends base.html."""
    base = base or base_url()
    return dict(page=page, canonical=page_url(base, page['path']) if page.get('path') else base + '/', og_image=base + OG_IMAGE_PATH,
                noindex=noindex, jsonld=None if noindex else jsonld(page, base), updated_display=display_date(page['updated']) if page.get('updated') else '')


# ---------------------------------------------------------------------------------------------------- generated files
def robots_txt(base):
    rules = ['Allow: /'] + [f'Disallow: {path}' for path in PRIVATE_PATHS]
    lines = [f'# {sc.BRAND} robots.txt', '# Search engines and AI assistants are welcome to read and cite the public pages.', '# The API and health checks are not content.', '']
    lines += ['User-agent: *'] + rules + ['']
    lines += ['# Search and AI assistant crawlers, listed explicitly'] + [f'User-agent: {bot}' for bot in CRAWLERS] + rules + ['']
    lines += [f'Sitemap: {base}/sitemap.xml', '']
    return '\n'.join(lines)


def indexable_pages():
    pages = list(sc.PAGES.values()) + list(sc.LEGAL.values())
    return sorted(pages, key=lambda p: (p['path'] != '/', p['path']))


def sitemap_xml(base):
    urls = ''.join(f'  <url>\n    <loc>{html.escape(page_url(base, p["path"]))}</loc>\n    <lastmod>{p["updated"]}</lastmod>\n  </url>\n' for p in indexable_pages())
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def llms_txt(base):
    home = sc.PAGES['/']
    lines = [f'# {sc.BRAND}', '', f'> {md_plain(home["lead"])}', '',
             f'{sc.BRAND} is not affiliated with Instagram, Meta, LinkedIn or Pinterest. It only handles public posts, never asks for a login, and does not store files.', '',
             '## Key facts', '',
             f'- Cost: free during the beta, no account.',
             f'- Platforms: Instagram (Reels, photos, carousels), LinkedIn (images, videos, carousel slides, lnkd.in links), Pinterest (original-size images, MP4 video pins, pin.it links).',
             f'- Limits: {sc.LIMITS["file_mb"]} MB per file, {sc.LIMITS["zip_mb"]} MB per ZIP, {sc.LIMITS["attachments"]} attachments per post.',
             f'- Privacy: files are deleted when the transfer ends; no accounts, cookies, ads or analytics.',
             f'- Last tested: {sc.TESTED_ON}, 17 of 17 real public post links downloaded and validated.', '', '## Downloaders', '']
    for path in ('/linkedin-downloader', '/pinterest-downloader', '/instagram-downloader'):
        p = sc.PAGES[path]
        lines.append(f'- [{p["eyebrow"]}]({page_url(base, path)}): {p["description"]}')
    lines += ['', '## About and policies', '',
              f'- [About and how it works]({base}/about): {sc.PAGES["/about"]["description"]}']
    for path, p in sc.LEGAL.items():
        lines.append(f'- [{p["name"]}]({base}{path}): {p["description"]}')
    lines += ['', '## Optional', '', f'- [Pricing and limits]({base}/pricing.md): free, with fair-use limits.',
              f'- [Full site text for LLMs]({base}/llms-full.txt): every page as markdown.', f'- [Sitemap]({base}/sitemap.xml)', f'- [Source code]({sc.GITHUB_URL})', '']
    return '\n'.join(lines)


def _section_markdown(section, base):
    out = []
    if section.get('heading'):
        out += [f'## {section["heading"]}', '']
    if section.get('intro'):
        out += [md_absolute(section['intro'], base), '']
    kind = section['type']
    if kind == 'steps':
        out += [f'{i}. **{name}**: {md_absolute(text, base)}' for i, (name, text) in enumerate(section['items'], 1)] + ['']
    elif kind == 'facts':
        out += [f'- **{label}**: {md_absolute(text, base)}' for label, text in section['items']] + ['']
    elif kind == 'table':
        out += ['| ' + ' | '.join(section['columns']) + ' |', '|' + '---|' * len(section['columns'])]
        out += ['| ' + ' | '.join(md_absolute(cell, base) for cell in row) + ' |' for row in section['rows']] + ['']
    elif kind == 'prose':
        out += [md_absolute(p, base) + '\n' for p in section['paragraphs']]
    elif kind == 'faq':
        for q, a in section['items']:
            out += [f'### {q}', '', md_absolute(a, base), '']
    elif kind == 'sources':
        out += [f'- [{title}]({url}): {note}' for title, url, note in section['items']] + ['']
    elif kind == 'features':
        out += [f'- **{title}**: {text}' for _img, _alt, _w, _h, _pos, _tag, title, text in section['items']] + ['']
    elif kind == 'cards':
        out += [f'- [{title}]({base}{path}): {text}' for _cls, _ic, title, path, text in section['items']] + ['']
    return out


def llms_full_txt(base):
    out = [f'# {sc.BRAND}: full site text', '', f'Last updated {display_date(sc.UPDATED)}. Source: {base}/', '']
    for path in ('/', '/linkedin-downloader', '/pinterest-downloader', '/instagram-downloader', '/about'):
        page = sc.PAGES[path]
        out += ['---', '', f'# {page["title"]}', f'URL: {page_url(base, path)}', '', md_absolute(page['lead'], base), '']
        for section in page['sections']:
            out += _section_markdown(section, base)
    return '\n'.join(out).rstrip() + '\n'


def pricing_md(base):
    return (f'# Pricing: {sc.BRAND}\n\n'
            f'{sc.BRAND} is free during its beta. There is no account, subscription, trial or paid tier.\n\n'
            '## Free\n\n- Price: $0\n- Account: not required\n'
            f'- Limits: {sc.LIMITS["file_mb"]} MB per file, {sc.LIMITS["zip_mb"]} MB per ZIP, {sc.LIMITS["attachments"]} attachments per post\n'
            f'- Fair use: {sc.LIMITS["lookups_per_min"]} lookups and {sc.LIMITS["downloads_per_min"]} downloads per minute per visitor\n'
            f'- Download links expire after {sc.LIMITS["session_minutes"]} minutes\n'
            '- Includes: Instagram, LinkedIn and Pinterest downloads, individual files and ZIP bundles, no watermark\n\n'
            f'Last updated {display_date(sc.UPDATED)}. See {base}/about for limits and how the tool works.\n')


def security_txt(base):
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    return f'Contact: mailto:{contact_email()}\nExpires: {expires}\nPreferred-Languages: en\nCanonical: {base}/.well-known/security.txt\n'


def manifest(base):
    return {'name': sc.BRAND, 'short_name': sc.BRAND, 'description': sc.PAGES['/']['description'], 'start_url': '/', 'scope': '/', 'display': 'browser',
            'background_color': '#f4f8ff', 'theme_color': '#f4f8ff', 'lang': 'en',
            'icons': [{'src': '/static/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                      {'src': LOGO_PATH, 'sizes': '512x512', 'type': 'image/png'}]}


# ---------------------------------------------------------------------------------------------------- flask wiring
def text_response(body, mimetype='text/plain', max_age=3600):
    response = Response(body, mimetype=mimetype)
    response.headers['Content-Type'] = f'{mimetype}; charset=utf-8'
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    return response


def conditional(response, body, max_age=300):
    """Add ETag and cache headers so crawlers and browsers can revalidate cheaply (304)."""
    response.set_etag(hashlib.md5(body.encode('utf-8')).hexdigest())
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    return response.make_conditional(request)


def render_content_page(path, is_public):
    page = sc.PAGES[path]
    base = base_url()
    key = (path, base, bool(is_public), sc.BRAND, os.environ.get('CONTACT_EMAIL', ''),
           os.environ.get('GOOGLE_SITE_VERIFICATION', ''), os.environ.get('BING_SITE_VERIFICATION', ''))
    body = _page_cache.get(key)
    if body is None:
        body = render_template(page['template'], is_public=bool(is_public), **page_meta(page, base))
        if len(_page_cache) > 64:
            _page_cache.clear()
        _page_cache[key] = body
    return conditional(Response(body, mimetype='text/html'), body)


def canonical_redirect():
    """301 to the canonical host (when SITE_URL is set) and to the slash-less form of a path."""
    if request.method not in ('GET', 'HEAD') or request.path in HEALTH_PATHS:
        return None
    explicit = os.environ.get('SITE_URL', '').strip().rstrip('/')
    parts = urlsplit(explicit) if explicit.startswith(('https://', 'http://')) else None
    path = request.path
    wrong_host = bool(parts and parts.netloc.lower() != request.host.lower())
    wrong_scheme = bool(parts and parts.scheme != request.scheme)
    trailing = len(path) > 1 and path.endswith('/')
    if not (wrong_host or wrong_scheme or trailing):
        return None
    # request.path is decoded: re-encode reserved characters so they cannot
    # become a query, fragment or a different path in the Location header.
    target = (explicit if parts else base_url()) + quote(path.rstrip('/') if trailing else path, safe='/')
    if request.query_string:
        target += '?' + request.query_string.decode('utf-8', 'replace')
    return redirect(target, code=301)


def init_app(app, is_public):
    """Register SEO routes and template helpers. is_public() is read per request (tests toggle it)."""
    app.jinja_env.filters['md'] = md_inline
    app.jinja_env.globals['asset'] = asset

    @app.context_processor
    def inject():
        return dict(site=site_info(base_url()), is_public=is_public())

    @app.before_request
    def seo_redirects():
        return canonical_redirect()

    for path in sc.PAGES:
        endpoint = 'page_' + (path.strip('/').replace('-', '_') or 'home')
        app.add_url_rule(path, endpoint, (lambda p=path: render_content_page(p, is_public())))

    @app.get('/robots.txt')
    def robots():
        return text_response(robots_txt(base_url()))

    @app.get('/sitemap.xml')
    def sitemap():
        return text_response(sitemap_xml(base_url()), 'application/xml')

    @app.get('/llms.txt')
    def llms():
        return text_response(llms_txt(base_url()))

    @app.get('/llms-full.txt')
    def llms_full():
        return text_response(llms_full_txt(base_url()))

    @app.get('/pricing.md')
    def pricing():
        return text_response(pricing_md(base_url()), 'text/markdown')

    @app.get('/.well-known/security.txt')
    def security():
        if not contact_email():
            return error_404()
        return text_response(security_txt(base_url()))

    @app.get(f'/{INDEXNOW_KEY}.txt')
    def indexnow_key():
        return text_response(INDEXNOW_KEY, max_age=86400)

    @app.get('/site.webmanifest')
    def webmanifest():
        response = jsonify(manifest(base_url()))
        response.headers['Content-Type'] = 'application/manifest+json; charset=utf-8'
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response

    @app.get('/favicon.ico')
    def favicon():
        response = send_from_directory(os.path.join(app.static_folder, 'icons'), 'favicon.ico', mimetype='image/x-icon')
        response.headers['Cache-Control'] = 'public, max-age=86400'
        return response

    def error_404(_error=None):
        if request.path.startswith('/api/'):
            return jsonify(error='Not found.'), 404
        page = dict(path='/404', title=f'Page not found | {sc.BRAND}', description='The page you are looking for does not exist.', updated=sc.UPDATED, kind='error',
                    breadcrumb=[])
        response = Response(render_template('404.html', is_public=is_public(), **page_meta(page, noindex=True)), status=404, mimetype='text/html')
        response.headers['X-Robots-Tag'] = 'noindex'
        return response

    app.register_error_handler(404, error_404)
