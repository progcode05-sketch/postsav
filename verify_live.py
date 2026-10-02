"""Opt-in real network checks. Fails on bad extraction, wrong counts or invalid files.

Usage: python verify_live.py [name-filter]. A filter (for example "Pinterest") runs only matching samples and does
not overwrite docs/live-test-results.json.
"""
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import app

SAMPLES = [
    ('LinkedIn short-link video', 'https://lnkd.in/p/dSMQHtWn', ['video']),
    ('LinkedIn short-link image', 'https://lnkd.in/p/dEm7VwWv', ['image']),
    ('LinkedIn image', 'https://www.linkedin.com/posts/rhea-space-activity_spacephotography-photography-nasa-activity-6986886128238784512-QUyP', ['image']),
    ('LinkedIn eight images', 'https://www.linkedin.com/posts/friends-of-nasa_nasa-csa-space-activity-7110625973888266241-bZ_g', ['image'] * 8),
    ('LinkedIn feed URL four images', 'https://www.linkedin.com/feed/update/urn:li:activity:7361048900801077248/', ['image'] * 4),
    ('LinkedIn video', 'https://www.linkedin.com/posts/the-mathworks_2_what-is-mathworks-cloud-center-activity-7151241570371948544-4Gu7', ['video']),
    ('LinkedIn document', 'https://www.linkedin.com/posts/richardvanderblom_how-to-create-the-perfect-carousel-post-on-activity-7138425457561006080-VOAi', ['image'] * 12),
    ('Instagram reel', 'https://www.instagram.com/reel/DdJW4CIOK6H/', ['video']),
    ('Instagram photo', 'https://www.instagram.com/p/BwFQEn0j7v1/', ['image']),
    ('Instagram video carousel', 'https://www.instagram.com/p/BQ0eAlwhDrw/', ['video'] * 3),
    ('Instagram image carousel', 'https://www.instagram.com/p/DJS2jZXptzr/', None),
    ('Pinterest short-link video (1)', 'https://pin.it/1Llt9HRdp', ['video']),
    ('Pinterest short-link video (2)', 'https://pin.it/55aPD5MCW', ['video']),
    ('Pinterest short-link video (3)', 'https://pin.it/1DdlFsoPF', ['video']),
    ('Pinterest short-link video (4)', 'https://pin.it/1nAsJSkh2', ['video']),
    ('Pinterest short-link image', 'https://pin.it/49lpVB04J', ['image']),
    ('Pinterest regional slug URL image', 'https://in.pinterest.com/pin/landing-page-with-services--11470174047344182/', ['image']),
]


def check_file(body, name):
    if name.endswith(('.jpg', '.png', '.webp', '.gif')):
        from PIL import Image
        with Image.open(io.BytesIO(body)) as image:
            image.verify()
    elif name.endswith('.mp4'):
        assert body[4:8] == b'ftyp', 'Invalid MP4 signature'
        assert b'mdat' in body and b'moov' in body, 'MP4 missing media or metadata'
    else:
        raise AssertionError(f'Unexpected output format: {name}')


def run(name_filter=''):
    client, results = app.app.test_client(), []
    for label, url, expected in SAMPLES:
        if name_filter.lower() not in label.lower():
            continue
        result = dict(label=label, url=url)
        try:
            r = client.post('/api/info', json={'url': url})
            assert r.status_code == 200, r.json
            data = r.json
            kinds = [a['kind'] for a in data['assets']]
            result.update(kinds=kinds, warnings=data['warnings'])
            if expected is not None:
                assert kinds == expected, f'Expected {expected}; got {kinds}'
            else:
                assert len(kinds) > 1 and 'image' in kinds, 'Expected image carousel'
            # Every individual attachment must download, not just the first one.
            total = 0
            for asset in data['assets']:
                d = client.get('/api/download', query_string={'session': data['session'], 'asset': asset['id']})
                assert d.status_code == 200, d.json
                mime = d.content_type
                ext = '.mp4' if mime == 'video/mp4' else '.jpg' if mime == 'image/jpeg' else '.png' if mime == 'image/png' else '.webp'
                check_file(d.data, ext)
                total += len(d.data)
                d.close()
            if len(kinds) > 1:
                d = client.get('/api/download', query_string={'session': data['session'], 'asset': 'all'})
                assert d.status_code == 200, d.json
                with zipfile.ZipFile(io.BytesIO(d.data)) as archive:
                    assert len(archive.namelist()) == len(kinds)
                    assert archive.testzip() is None
                    for name in archive.namelist():
                        check_file(archive.read(name), name)
                d.close()
            result.update(status='PASS', bytes=total)
        except Exception as err:
            result.update(status='FAIL', error=str(err))
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)
    report = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), results=results)
    if not name_filter:
        Path('docs/live-test-results.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
    return 1 if any(r['status'] != 'PASS' for r in results) else 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else ''))
