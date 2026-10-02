"""Platform extraction, independent of Flask and download-session storage."""
import json
import os
import re
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

MAX_FETCH = 12 * 1024 * 1024
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}


def allowed_url(url, platform, page=False):
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
            return False
    except ValueError:
        return False
    host = (p.hostname or '').lower()
    domains = ('linkedin.com',) if page else (('licdn.com',) if platform == 'linkedin' else ('cdninstagram.com', 'fbcdn.net'))
    return any(host == d or host.endswith('.' + d) for d in domains)


def fetch(url, platform, limit=MAX_FETCH, page=False):
    """Validate every redirect and bound memory use; never accept arbitrary media URLs."""
    for _ in range(5):
        if not allowed_url(url, platform, page):
            raise ValueError('The media source returned an unsupported download host.')
        with requests.get(url, headers=HEADERS, timeout=(10, 35), stream=True, allow_redirects=False) as r:
            if r.is_redirect:
                from urllib.parse import urljoin
                url = urljoin(url, r.headers['Location'])
                continue
            r.raise_for_status()
            chunks, size = [], 0
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('This file exceeds the download size limit.')
                chunks.append(chunk)
            return b''.join(chunks), r.headers.get('Content-Type', '').split(';')[0]
    raise ValueError('Too many redirects from the media source.')


def download_to_path(url, platform, path, limit):
    """Stream trusted media to disk without buffering the file in process memory."""
    for _ in range(5):
        if not allowed_url(url, platform):
            raise ValueError('The media source returned an unsupported download host.')
        with requests.get(url, headers=HEADERS, timeout=(10, 60), stream=True, allow_redirects=False) as response:
            if response.is_redirect:
                from urllib.parse import urljoin
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            declared_size = response.headers.get('Content-Length')
            if declared_size:
                try:
                    if int(declared_size) > limit:
                        raise ValueError('This file exceeds the download size limit.')
                except (TypeError, ValueError) as error:
                    if isinstance(error, ValueError) and str(error).startswith('This file'):
                        raise
            size = 0
            try:
                with open(path, 'wb') as output:
                    for chunk in response.iter_content(64 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > limit:
                            raise ValueError('This file exceeds the download size limit.')
                        output.write(chunk)
            except Exception:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                raise
            return size, response.headers.get('Content-Type', '').split(';')[0]
    raise ValueError('Too many redirects from the media source.')


def linkedin_post(url):
    raw, _ = fetch(url, 'linkedin', page=True)
    soup = BeautifulSoup(raw, 'html.parser')
    post = soup.select_one('.main-feed-activity-card[data-activity-urn]')
    if not post:
        raise ValueError('LinkedIn did not expose this post. It may require sign-in, be private, or be temporarily blocked.')
    meta = lambda key: (soup.find('meta', property=key) or {}).get('content', '')
    assets, warnings = [], []
    uploader = ''
    post_records = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            structured = json.loads(script.string or script.get_text())
            records = structured if isinstance(structured, list) else [structured]
            for record in records:
                if record.get('@type') in ('SocialMediaPosting', 'VideoObject'):
                    author = record.get('author') or record.get('creator') or {}
                    uploader = author.get('name', '') if isinstance(author, dict) else ''
                    post_records.append(record)
        except (ValueError, AttributeError):
            pass
    def add(kind, source, thumb=None, label=None):
        if allowed_url(source, 'linkedin') and not any(a['source'] == source for a in assets):
            thumbnail = thumb if allowed_url(thumb, 'linkedin') else (source if kind == 'image' else None)
            assets.append(dict(kind=kind, source=source, thumbnail=thumbnail, label=label))
    # The public grid shows at most five images; JSON-LD includes the full ordered set.
    target_ids = set(re.findall(r'(?:activity|ugcPost|share)[:-](\d+)', url))
    card_ids = set(re.findall(r'(?:activity|ugcPost|share):(\d+)', ' '.join(str(post.get(k, '')) for k in ('data-activity-urn', 'data-attributed-urn'))))
    if target_ids and not target_ids.intersection(card_ids):
        raise ValueError('LinkedIn returned a different post. Please copy the original post URL and try again.')
    for record in post_records:
        record_id = record.get('@id', '')
        if record_id and target_ids and not any(value in record_id for value in target_ids):
            continue
        images = record.get('image') or []
        images = images if isinstance(images, list) else [images]
        for image in images:
            source = image.get('url') if isinstance(image, dict) else image
            native_images = post.select_one('.feed-images-content')
            if isinstance(source, str) and (re.search(r'/feedshare-(?:shrink|image-high-res)', source) or (native_images and '/image-shrink_' in source)):
                add('image', source, label=f'Image {len(assets) + 1}')
    for video in post.select('video[data-sources]'):
        try:
            sources = json.loads(video['data-sources'])
            mp4 = [s for s in sources if isinstance(s, dict) and s.get('type') == 'video/mp4' and allowed_url(s.get('src'), 'linkedin')]
        except (ValueError, TypeError):
            warnings.append('One video could not be extracted from this post.')
            continue
        if mp4:
            def bitrate(source):
                try:
                    return float(source.get('data-bitrate') or 0)
                except (ValueError, TypeError):
                    return 0
            best = max(mp4, key=bitrate)
            add('video', best['src'], video.get('data-poster-url'), 'Video')
    for image in post.select('img'):
        source = image.get('data-delayed-url') or image.get('src')
        # Attachment paths only: excludes avatars, logos, link cards and video posters.
        if source and (re.search(r'/feedshare-(?:shrink|image-high-res)', source) or ('/image-shrink_' in source and image.find_parent(class_='feed-images-content'))):
            alt = image.get('alt') or ''
            add('image', source, label=alt if alt and not alt.startswith('No alternative text') else f'Image {len(assets) + 1}')
    for frame in post.select('[data-native-document-config]'):
        doc = {}
        try:
            doc = json.loads(frame['data-native-document-config']).get('doc', {})
            manifest = json.loads(fetch(doc.get('manifestUrl') or doc.get('url'), 'linkedin')[0])
            resolutions = manifest.get('perResolutions') or []
            best = max(resolutions, key=lambda r: r.get('width', 0))
            pages = json.loads(fetch(best['imageManifestUrl'], 'linkedin')[0]).get('pages', [])
            if not isinstance(pages, list) or not pages:
                raise ValueError('No carousel pages were exposed.')
            for i, page in enumerate(pages, 1):
                add('image', page, label=f'Carousel slide {i}')
            if sum(allowed_url(page, 'linkedin') for page in pages) != doc.get('totalPageCount', len(pages)):
                warnings.append('LinkedIn exposed only some carousel slides.')
            # Honor download availability. Never expose a scan-gated PDF as downloadable.
            pdf = manifest.get('downloadUrl') or manifest.get('transcribedDocumentUrl')
            if pdf and not manifest.get('scanRequiredForDownload', True):
                add('document', pdf, label='Carousel PDF')
            else:
                warnings.append('The original document requires LinkedIn sign-in; available slides can be saved as images or ZIP.')
        except (ValueError, KeyError, TypeError, AttributeError, requests.RequestException):
            warnings.append('The full carousel could not be fetched. Only exposed cover slides are available.')
            for i, page in enumerate(doc.get('coverPages', []), 1):
                add('image', page.get('config', {}).get('src'), label=f'Cover slide {i}')
    if not assets:
        raise ValueError('No downloadable attachments were exposed by LinkedIn. Text posts, external link previews, and restricted posts are not supported.')
    return dict(platform='linkedin', url=url, title=meta('og:description')[:140] or meta('og:title'), uploader=uploader or 'LinkedIn post', assets=assets, warnings=warnings)


def instagram_post(url, ydl_opts):
    import yt_dlp
    warnings = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)
        entries = data.get('entries') if data.get('_type') == 'playlist' else [data]
        assets = []
        for i, e in enumerate(entries or []):
            if not e:
                continue
            direct = e.get('url')
            # Reuse extracted combined MP4 URLs; re-extraction can trigger rate limits.
            if allowed_url(direct, 'instagram') and e.get('ext') == 'mp4' and not e.get('requested_formats'):
                assets.append(dict(kind='video', source=direct, thumbnail=e.get('thumbnail'), label=f'Video {i + 1}'))
            else:
                assets.append(dict(kind='video', source=url, entry=i + 1, thumbnail=e.get('thumbnail'), label=f'Video {i + 1}'))
    except Exception:
        data, assets = {}, []
    if assets and '/p/' not in url:
        return dict(platform='instagram', url=url, title=(data.get('description') or data.get('title') or 'Instagram reel')[:140], uploader=data.get('uploader') or '', assets=assets, warnings=[])
    # Instaloader exposes both photo and video nodes, including mixed carousels.
    try:
        import instaloader
        loader = instaloader.Instaloader(max_connection_attempts=1, request_timeout=25, quiet=True)
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            loader.context._session.cookies.update(ydl.cookiejar)
        post = instaloader.Post.from_shortcode(loader.context, url.rstrip('/').split('/')[-1])
        nodes = list(post.get_sidecar_nodes()) if post.typename == 'GraphSidecar' else [post]
        candidate_assets = [dict(kind='video' if node.is_video else 'image', source=node.video_url if node.is_video else (node.display_url if hasattr(node, 'display_url') else node.url), thumbnail=node.display_url if hasattr(node, 'display_url') else post.url, label=f'{"Video" if node.is_video else "Image"} {i + 1}') for i, node in enumerate(nodes)]
        if not candidate_assets or any(not allowed_url(a['source'], 'instagram') for a in candidate_assets):
            raise ValueError('Instagram returned unavailable media URLs.')
        data.update(description=post.caption, uploader=post.owner_username)
        assets = candidate_assets
    except Exception:
        if not assets:
            raise ValueError('Instagram did not expose media for this post. Try a public post. When running locally, Instagram cookie setup is described in the README.')
        warnings.append('Only videos could be extracted. Any photo attachments in this post may be missing; Instagram may require a login session.')
    return dict(platform='instagram', url=url, title=(data.get('description') or data.get('title') or 'Instagram post')[:140], uploader=data.get('uploader') or '', assets=assets, warnings=warnings)
