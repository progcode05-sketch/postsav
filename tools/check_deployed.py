"""Smoke-test an actual deployed server, including validated media and ZIP files.

Usage: python tools/check_deployed.py https://your-site.example
Uses three historical public samples; platform availability can change.
"""
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image


def validate_media(body, name):
    if name.endswith('.mp4'):
        assert body[4:8] == b'ftyp' and b'moov' in body and b'mdat' in body, 'Invalid MP4 container'
    else:
        with Image.open(io.BytesIO(body)) as image:
            image.verify()


def run(site):
    results = []
    client = requests.Session()

    def record(name, check):
        try:
            detail = check()
            result = dict(name=name, status='PASS', detail=detail)
        except Exception as error:
            result = dict(name=name, status='FAIL', error=str(error))
        results.append(result)
        print(json.dumps(result), flush=True)

    def api(path, expected, method='GET', **kwargs):
        response = client.request(method, site + path, timeout=(10, 150), **kwargs)
        assert response.status_code == expected, f'HTTP {response.status_code}: {response.text[:300]}'
        assert 'no-store' in response.headers.get('Cache-Control', ''), 'API response can be cached'
        assert 'noindex' in response.headers.get('X-Robots-Tag', ''), 'API response can be indexed'
        return response

    record('ownership acknowledgment', lambda: api('/api/info', 400, 'POST', json={'url': 'https://www.instagram.com/p/ABC/'}).json())
    record('invalid URL', lambda: api('/api/info', 400, 'POST', json={'url': 'https://example.com', 'ack': True}).json())
    record('expired session', lambda: api('/api/download?session=expired&asset=0', 410).json())
    record('unknown API route', lambda: api('/api/missing', 404).json())

    samples = [
        ('LinkedIn image carousel', 'https://www.linkedin.com/posts/friends-of-nasa_nasa-csa-space-activity-7110625973888266241-bZ_g', 'image', 8),
        ('Pinterest image', 'https://in.pinterest.com/pin/landing-page-with-services--11470174047344182/', 'image', 1),
        ('Instagram reel', 'https://www.instagram.com/reel/DdJW4CIOK6H/', 'video', 1),
    ]

    def media(url, kind, count):
        data = api('/api/info', 200, 'POST', json={'url': url, 'ack': True}).json()
        assert len(data['assets']) == count, f"Expected {count} assets, got {len(data['assets'])}"
        assert all(asset['kind'] == kind for asset in data['assets']), 'Unexpected media kind'
        params = {'session': data['session'], 'asset': '0'}
        response = api('/api/download', 200, params=params)
        assert 'attachment;' in response.headers.get('Content-Disposition', ''), 'Missing download filename'
        validate_media(response.content, '.mp4' if kind == 'video' else '.jpg')
        size = len(response.content)
        if count > 1:
            response = api('/api/download', 200, params={**params, 'asset': 'all'})
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert len(archive.namelist()) == count, 'Missing ZIP entries'
                assert archive.testzip() is None, 'ZIP CRC failure'
                for name in archive.namelist():
                    validate_media(archive.read(name), name)
            size += len(response.content)
        return dict(assets=count, validated_bytes=size, warnings=data.get('warnings', []))

    for label, url, kind, count in samples:
        record(label, lambda u=url, k=kind, c=count: media(u, k, c))
    report = dict(site=site, checked_at_utc=datetime.now(timezone.utc).isoformat(), results=results)
    destination = Path(__file__).resolve().parents[1] / 'docs' / 'deployed-check-results.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return int(any(result['status'] == 'FAIL' for result in results))


if __name__ == '__main__':
    if len(sys.argv) != 2 or not sys.argv[1].startswith('https://'):
        raise SystemExit(__doc__)
    raise SystemExit(run(sys.argv[1].rstrip('/')))
