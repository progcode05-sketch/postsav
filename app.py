"""Social media downloader. Run python app.py locally; Gunicorn serves wsgi:application in production."""
import ipaddress
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import sys
import zipfile
import logging
import socket
from urllib.parse import quote, urlsplit, unquote

from flask import Flask, Response, abort, jsonify, render_template, request, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import yt_dlp
from media_sources import download_to_path, linkedin_post, instagram_post
from limits import DownloadGate, RateLimiter


def env_int(name, default):
    try:
        return int(os.environ.get(name, '').strip() or default)
    except ValueError:
        return default


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8192
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, 'cookies.txt')
BROWSER = os.environ.get('IG_BROWSER', '').strip().lower()
# Public mode is for the shared deployment: personal cookies are never used,
# the ownership acknowledgment is required and abuse limits default to on.
PUBLIC_MODE = os.environ.get('PUBLIC_MODE', '').strip().lower() in ('1', 'true', 'yes', 'on')
HAS_FFMPEG = shutil.which('ffmpeg') is not None
MAX_FILE = 250 * 1024 * 1024
MAX_BUNDLE = 500 * 1024 * 1024
SESSION_TTL = 15 * 60
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), 'social_downloader')
STALE_DOWNLOAD_AGE = env_int('STALE_DOWNLOAD_AGE', 15 * 60)
CLEANUP_INTERVAL = env_int('CLEANUP_INTERVAL', 5 * 60)
DISK_BUDGET = env_int('DISK_BUDGET_MB', 1536) * 1024 * 1024
MIN_FREE_DISK = env_int('MIN_FREE_DISK_MB', 300) * 1024 * 1024
# 0 disables a limit. Defaults are strict in public mode and off locally.
RATE_INFO_PER_MIN = env_int('RATE_INFO_PER_MIN', 10 if PUBLIC_MODE else 0)
RATE_DOWNLOAD_PER_MIN = env_int('RATE_DOWNLOAD_PER_MIN', 30 if PUBLIC_MODE else 0)
MAX_CONCURRENT_DOWNLOADS = env_int('MAX_CONCURRENT_DOWNLOADS', 2 if PUBLIC_MODE else 4)
MAX_DOWNLOADS_PER_CLIENT = env_int('MAX_DOWNLOADS_PER_CLIENT', 1 if PUBLIC_MODE else 4)
REDIS_URL = os.environ.get('REDIS_URL', '').strip()
OPERATOR_NAME = os.environ.get('OPERATOR_NAME', '').strip()
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', '').strip()
# Header carrying the real client address when the host sits behind a CDN, e.g. CF-Connecting-IP on Render.
CLIENT_IP_HEADER = os.environ.get('CLIENT_IP_HEADER', '').strip()
sessions = {}
session_lock = threading.Lock()
rate_limiter = RateLimiter()
download_gate = DownloadGate()
_redis_client = None
_background_started = False
_background_lock = threading.Lock()

# The shared host's proxy supplies the real client address in X-Forwarded-For.
# TRUSTED_PROXY_HOPS is how many proxies to trust (default 1 in public mode).
_proxy_hops = env_int('TRUSTED_PROXY_HOPS', 1 if PUBLIC_MODE else 0)
if _proxy_hops > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_proxy_hops, x_proto=_proxy_hops, x_host=_proxy_hops)

if PUBLIC_MODE and (os.path.exists(COOKIE_FILE) or BROWSER):
    logging.getLogger(__name__).warning('PUBLIC_MODE ignores cookies.txt and IG_BROWSER; personal cookies are never used on a shared server.')


class ExtractionLogger:
    """Fallback extraction errors are diagnostics, not failed user requests."""
    def debug(self, message):
        logging.getLogger('media.extractor').debug(message)

    warning = debug
    error = debug


def ydl_opts(extra=None):
    opts = dict(quiet=True, no_warnings=True, noprogress=True, noplaylist=True, logger=ExtractionLogger(),
                socket_timeout=30, retries=2, max_filesize=MAX_FILE,
                format='b[ext=mp4]/bv*[ext=mp4]+ba[ext=m4a]/b' if HAS_FFMPEG else 'b[ext=mp4]/b', merge_output_format='mp4')
    if not PUBLIC_MODE:
        if os.path.exists(COOKIE_FILE):
            opts['cookiefile'] = COOKIE_FILE
        elif BROWSER:
            opts['cookiesfrombrowser'] = (BROWSER,)
    opts.update(extra or {})
    return opts


def clean_url(raw):
    if not isinstance(raw, str) or len(raw) > 2048:
        return None
    try:
        p = urlsplit(raw.strip())
        if p.scheme not in ('http', 'https') or p.username or p.password or p.port not in (None, 80, 443):
            return None
        path = unquote(p.path)
        if p.hostname in ('lnkd.in', 'www.lnkd.in'):
            if re.fullmatch(r'/p/[A-Za-z0-9_-]{4,64}/?', path):
                return resolve_linkedin_short_url(f'https://lnkd.in{path.rstrip("/")}')
            return None
        if p.hostname in ('instagram.com', 'www.instagram.com', 'm.instagram.com'):
            m = re.fullmatch(r'/(?:[A-Za-z0-9._]+/)?(reel|reels|p|tv)/([A-Za-z0-9_-]+)/?', path)
            if m:
                kind = 'reel' if m[1] == 'reels' else m[1]
                return f'https://www.instagram.com/{kind}/{m[2]}/'
        if p.hostname in ('linkedin.com', 'www.linkedin.com', 'm.linkedin.com'):
            if re.fullmatch(r'/posts/[A-Za-z0-9_-]+-(?:activity|ugcPost|share)-\d+-[A-Za-z0-9_-]+/?', path) or re.fullmatch(r'/feed/update/urn:li:(?:activity|ugcPost|share):\d+/?', path):
                return 'https://www.linkedin.com' + path.rstrip('/')
    except ValueError:
        pass
    return None


def resolve_linkedin_short_url(url):
    """Resolve only LinkedIn's post short links, validating every redirect."""
    current = url
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
    try:
        for _ in range(5):
            parsed = urlsplit(current)
            host = (parsed.hostname or '').lower()
            if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
                return None
            if host not in ('lnkd.in', 'www.lnkd.in', 'linkedin.com', 'www.linkedin.com', 'm.linkedin.com'):
                return None
            if host not in ('lnkd.in', 'www.lnkd.in'):
                # Avoid resolving a full post twice; clean_url strips tracking parameters.
                return clean_url(current)
            response = requests.get(current, headers=headers, timeout=(5, 15), allow_redirects=False, stream=True)
            try:
                if not response.is_redirect or not response.headers.get('Location'):
                    return None
                from urllib.parse import urljoin
                current = urljoin(current, response.headers['Location'])
            finally:
                response.close()
    except (requests.RequestException, ValueError):
        return None
    return None


def safe_name(text):
    return re.sub(r'[^\w\-]+', '_', str(text or '')).strip('_')[:60] or 'post'


def post_name(post):
    path = urlsplit(post['url']).path.rstrip('/')
    match = re.search(r'(?:activity|ugcPost|share)[:-](\d+)', path)
    identifier = match[1] if match else path.split('/')[-1]
    return f'{post["platform"]}_{safe_name(post["uploader"])}_{safe_name(identifier)}'


def friendly_error(err):
    if isinstance(err, ValueError):
        return str(err)
    msg = str(err).lower()
    if any(s in msg for s in ('login required', 'log in', 'rate-limit', 'cookies', 'empty media response')):
        if PUBLIC_MODE:
            return 'The platform requires sign-in or has limited this request, so this post cannot be fetched right now. Try a public post or try again later.'
        return 'The platform requires sign-in or has limited this request. Try again later; for local Instagram use, see cookie setup in README.'
    return 'Could not fetch this media. The post may be restricted or the platform may be blocking requests. Try again later.'


def redis_client():
    """Return the shared Redis client, or None when Redis is not configured."""
    global _redis_client
    if not REDIS_URL:
        return None
    if _redis_client is None:
        import redis
        _redis_client = redis.Redis.from_url(REDIS_URL, socket_timeout=2, socket_connect_timeout=2, decode_responses=True)
    return _redis_client


def remember(post):
    token = secrets.token_urlsafe(24)
    try:
        client = redis_client()
        if client is not None:
            client.set(f'social-downloader:session:{token}', json.dumps(post), ex=SESSION_TTL)
            return token
    except Exception as err:
        # Degrade to this process's memory rather than failing the user's request.
        app.logger.warning('Redis session store unavailable (%s); using process memory.', type(err).__name__)
    with session_lock:
        now = time.monotonic()
        for key in list(sessions):
            if sessions[key][0] <= now:
                del sessions[key]
        if len(sessions) >= 100:
            del sessions[next(iter(sessions))]
        sessions[token] = (now + SESSION_TTL, post)
    return token


def get_session(token):
    """Return the stored post for a session token, or None if missing/expired."""
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,64}', token):
        return None
    try:
        client = redis_client()
        if client is not None:
            raw = client.get(f'social-downloader:session:{token}')
            if raw:
                return json.loads(raw)
    except Exception as err:
        app.logger.warning('Redis session lookup failed (%s); checking process memory.', type(err).__name__)
    with session_lock:
        entry = sessions.get(token)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    return None


def client_ip():
    if CLIENT_IP_HEADER:
        value = request.headers.get(CLIENT_IP_HEADER, '').split(',')[0].strip()
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            pass
    return request.remote_addr or 'unknown'


def downloads_size():
    total = 0
    for root, _dirs, files in os.walk(DOWNLOAD_DIR):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def out_of_space():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    return downloads_size() > DISK_BUDGET or shutil.disk_usage(DOWNLOAD_DIR).free < MIN_FREE_DISK


def cleanup_stale_downloads():
    """Remove abandoned download jobs left by restarts or disconnected clients."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cutoff = time.time() - STALE_DOWNLOAD_AGE
    for name in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def start_background_cleanup():
    """Start the periodic stale-job sweeper once per process; it also sweeps at startup."""
    global _background_started
    with _background_lock:
        if _background_started:
            return
        _background_started = True

    def loop():
        while True:
            try:
                cleanup_stale_downloads()
            except Exception:
                app.logger.exception('Scheduled download cleanup failed')
            time.sleep(CLEANUP_INTERVAL)

    threading.Thread(target=loop, name='download-cleanup', daemon=True).start()


def new_download_dir():
    cleanup_stale_downloads()
    return tempfile.mkdtemp(prefix='job_', dir=DOWNLOAD_DIR)


def asset_file(post, asset, index, workdir):
    """Stream one server-extracted attachment into a bounded temporary directory."""
    kind = asset['kind']
    if asset.get('entry'):
        opts = ydl_opts(dict(outtmpl=os.path.join(workdir, '%(id)s.%(ext)s'), playlist_items=str(asset['entry']), noplaylist=False))
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(post['url'], download=True)
        files = [os.path.join(workdir, f) for f in os.listdir(workdir) if f.endswith(('.mp4', '.webm', '.mkv'))]
        if len(files) != 1:
            raise ValueError('The selected video could not be downloaded. Fetch the post again.')
        path = files[0]
        if os.path.getsize(path) > MAX_FILE:
            raise ValueError('This video exceeds the download size limit.')
        ext = os.path.splitext(path)[1]
        mime = 'video/mp4' if ext == '.mp4' else 'video/webm' if ext == '.webm' else 'video/x-matroska'
    else:
        path = os.path.join(workdir, f'asset_{index:03d}.download')
        _, mime = download_to_path(asset['source'], post['platform'], path, MAX_FILE)
        extensions = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif', 'video/mp4': '.mp4', 'application/pdf': '.pdf'}
        ext = extensions.get(mime)
        if not ext or not mime.startswith({'image': 'image/', 'video': 'video/', 'document': 'application/pdf'}[kind]):
            raise ValueError('The platform returned an unexpected file type. Fetch the post again.')
    name = f'{post_name(post)}_{index + 1:03d}{ext}'
    return path, name, mime


def stream_download(path, workdir, name, mime, release=None):
    """Yield a disk-backed response; the job directory and download slot are always released."""
    size = os.path.getsize(path)
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', '_', name) or 'download'

    def generate():
        with open(path, 'rb') as source:
            while chunk := source.read(64 * 1024):
                yield chunk

    disposition = f"attachment; filename={ascii_name}; filename*=UTF-8''{quote(name)}"
    response = Response(stream_with_context(generate()), mimetype=mime, headers={
        'Content-Disposition': disposition,
        'Content-Length': str(size),
    })

    def cleanup():
        # call_on_close also runs when a client disconnects before the body starts.
        shutil.rmtree(workdir, ignore_errors=True)
        if release:
            release()

    response.call_on_close(cleanup)
    return response


@app.before_request
def guard_requests():
    start_background_cleanup()
    limit = {'/api/info': RATE_INFO_PER_MIN, '/api/download': RATE_DOWNLOAD_PER_MIN}.get(request.path)
    if limit:
        allowed, retry = rate_limiter.check((request.path, client_ip()), limit)
        if not allowed:
            response = jsonify(error='Too many requests. Please wait a minute and try again.')
            response.status_code = 429
            response.headers['Retry-After'] = str(retry)
            return response


@app.get('/')
def index():
    return render_template('index.html', public_mode=PUBLIC_MODE)


LEGAL_PAGES = {'terms': 'Terms of Use', 'privacy': 'Privacy Policy', 'copyright': 'Copyright and Takedown', 'contact': 'Contact'}


@app.get('/<page>')
def legal(page):
    if page not in LEGAL_PAGES:
        abort(404)
    return render_template('legal.html', page=page, title=LEGAL_PAGES[page], pages=LEGAL_PAGES, operator=OPERATOR_NAME,
                           email=CONTACT_EMAIL, ttl=SESSION_TTL // 60, stale=STALE_DOWNLOAD_AGE // 60)


@app.get('/healthz')
def healthz():
    """Liveness: the process is up and serving. Cheap enough for a free uptime monitor."""
    return jsonify(status='ok')


@app.get('/readyz')
def readyz():
    """Readiness: working storage, Redis (when configured) and legal contact settings."""
    checks = {}
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        probe = os.path.join(DOWNLOAD_DIR, '.ready')
        with open(probe, 'w') as handle:
            handle.write('ok')
        os.remove(probe)
        checks['storage'] = shutil.disk_usage(DOWNLOAD_DIR).free >= MIN_FREE_DISK
    except OSError:
        checks['storage'] = False
    if REDIS_URL:
        try:
            checks['redis'] = bool(redis_client().ping())
        except Exception:
            checks['redis'] = False
    ready = all(checks.values())
    body = dict(status='ready' if ready else 'degraded', checks=checks, active_downloads=download_gate.active,
                ffmpeg=HAS_FFMPEG, public_mode=PUBLIC_MODE, legal_contact_configured=bool(CONTACT_EMAIL))
    return jsonify(body), 200 if ready else 503


@app.post('/api/info')
def info():
    payload = request.get_json(silent=True)
    if PUBLIC_MODE and not (isinstance(payload, dict) and payload.get('ack') is True):
        return jsonify(error='Please confirm that you own this content or have permission to download it.'), 400
    url = clean_url(payload.get('url') if isinstance(payload, dict) else None)
    if not url:
        return jsonify(error='Paste an Instagram reel/post URL or a LinkedIn post URL.'), 400
    try:
        post = linkedin_post(url) if 'linkedin.com' in urlsplit(url).hostname else instagram_post(url, ydl_opts)
        if not post['assets']:
            raise ValueError('No downloadable attachments were found in this post.')
        if len(post['assets']) > 100:
            raise ValueError('This post exceeds the limit of 100 attachments.')
        token = remember(post)
        public = {k: v for k, v in post.items() if k != 'assets'}
        public['session'] = token
        public['assets'] = [dict(id=str(i), kind=a['kind'], thumbnail=a.get('thumbnail'), label=a.get('label') or a['kind'].title()) for i, a in enumerate(post['assets'])]
        return jsonify(public)
    except Exception as err:
        app.logger.warning('Extraction failed for %s: %s', urlsplit(url).hostname, type(err).__name__)
        return jsonify(error=friendly_error(err)), 502


def busy(message, retry):
    response = jsonify(error=message)
    response.status_code = 503
    response.headers['Retry-After'] = str(retry)
    return response


@app.get('/api/download')
def download():
    post = get_session(request.args.get('session', ''))
    if not post:
        return jsonify(error='This download session expired. Fetch the post again.'), 410
    chosen = request.args.get('asset', '0')
    if chosen != 'all' and (not re.fullmatch(r'[0-9]{1,3}', chosen) or int(chosen) >= len(post['assets'])):
        return jsonify(error='Invalid attachment.'), 400
    release = download_gate.acquire(client_ip(), MAX_CONCURRENT_DOWNLOADS, MAX_DOWNLOADS_PER_CLIENT)
    if release is None:
        return busy('The server is busy preparing other downloads. Please try again in a moment.', 10)
    workdir = None
    try:
        if out_of_space():
            cleanup_stale_downloads()
            if out_of_space():
                release()
                return busy('The server is temporarily out of working space. Please try again shortly.', 30)
        workdir = new_download_dir()
        if chosen == 'all':
            archive_path = os.path.join(workdir, 'bundle.zip')
            total = 0
            with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for i, asset in enumerate(post['assets']):
                    path, name, _ = asset_file(post, asset, i, workdir)
                    total += os.path.getsize(path)
                    if total > MAX_BUNDLE:
                        raise ValueError('This bundle exceeds 500 MB. Download attachments individually.')
                    archive.write(path, arcname=name)
                    os.remove(path)
            return stream_download(archive_path, workdir, f'{post_name(post)}.zip', 'application/zip', release)
        i = int(chosen)
        path, name, mime = asset_file(post, post['assets'][i], i, workdir)
        return stream_download(path, workdir, name, mime, release)
    except Exception as err:
        release()
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        return jsonify(error=friendly_error(err)), 502


@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.path.startswith('/api/') or request.path in ('/healthz', '/readyz'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error='The submitted request is too large. Paste only the post URL.'), 413


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    # Prevent Windows from leaving two Flask processes on the same local port,
    # which can make requests alternate between old and new code.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            print(f'Port {port} is already in use. Close the existing downloader terminal with Ctrl+C, then start it again.')
            raise SystemExit(1)
    start_background_cleanup()
    if '--open-browser' in sys.argv:
        def open_when_ready():
            import urllib.request
            import webbrowser
            browser_url = f'http://127.0.0.1:{port}'
            for _ in range(40):
                try:
                    with urllib.request.urlopen(browser_url, timeout=1):
                        webbrowser.open(browser_url)
                    return
                except OSError:
                    time.sleep(0.25)
        threading.Thread(target=open_when_ready, daemon=True).start()
    app.run(host=host, port=port, debug=False)
