"""Offline tests for Pinterest pin support: URL handling, short links, extraction and downloads."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import app
import media_sources
from media_sources import allowed_url, pinterest_pin_url, pinterest_post

PIN_ID = '933230354048220904'
PIN_URL = f'https://www.pinterest.com/pin/{PIN_ID}/'
VIDEO_HASH = '95bae27226625b9332c3ac6ccb06e9df'
MP4 = f'https://v1.pinimg.com/videos/iht/expMp4/95/ba/e2/{VIDEO_HASH}_720w.mp4'
HLS = f'https://v1.pinimg.com/videos/iht/hls/95/ba/e2/{VIDEO_HASH}.m3u8'
THUMB = f'https://i.pinimg.com/videos/thumbnails/originals/95/ba/e2/{VIDEO_HASH}.0000000.jpg'
ORIGINAL = 'https://i.pinimg.com/originals/8f/87/fc/8f87fc02ca30266c6c75e673f4468ef1.png'
REDUCED = 'https://i.pinimg.com/736x/8f/87/fc/8f87fc02ca30266c6c75e673f4468ef1.jpg'


def page(posting=None, video=None, og_title='Modern Tennis Landing Page | Web design | Tennis poster', og_image=REDUCED, extra=''):
    scripts = ''.join(f'<script data-rh="true" type="application/ld+json">{json.dumps(record)}</script>' for record in (posting, video) if record)
    return (f'<html><head><meta property="og:title" content="{og_title}"><meta property="og:image" content="{og_image}"></head>'
            f'<body>{extra}{scripts}</body></html>').encode()


def posting(image=ORIGINAL, headline='Motion inspiration - Clip', author='Some Creator'):
    return {'@type': 'SocialMediaPosting', 'headline': headline, 'image': image, 'author': {'@type': 'Person', 'name': author}}


def video(content=MP4, thumb=THUMB, name='Motion inspiration - Clip'):
    return {'@type': 'VideoObject', 'name': name, 'contentUrl': content, 'thumbnailUrl': thumb, 'creator': {'@type': 'Person', 'name': 'Some Creator'}}


def extract(html):
    with patch('media_sources.fetch', return_value=(html, 'text/html')) as fetch:
        post = pinterest_post(PIN_URL)
    fetch.assert_called_once_with(PIN_URL, 'pinterest', page=True)
    return post


class PinUrlTests(unittest.TestCase):
    def test_pin_urls_normalize_to_one_form_and_drop_tracking(self):
        pin = f'https://www.pinterest.com/pin/{PIN_ID}/'
        for url in (pin, f'http://pinterest.com/pin/{PIN_ID}', f'https://www.pinterest.com/pin/{PIN_ID}/?utm_source=x#frag',
                    f'https://in.pinterest.com/pin/motion-inspiration-clip-video--{PIN_ID}/', f'https://pinterest.co.uk/pin/{PIN_ID}/',
                    f'https://uk.pinterest.com/pin/{PIN_ID}/sent/?invite_code=abc&sender=12345&sfo=1', f'https://www.pinterest.com.au/pin/{PIN_ID}'):
            self.assertEqual(pinterest_pin_url(url), pin, url)
            self.assertEqual(app.clean_url(url), pin, url)

    def test_sender_and_invite_codes_never_survive(self):
        cleaned = app.clean_url(f'https://www.pinterest.com/pin/{PIN_ID}/sent/?invite_code=secret&sender=1113374476537736733&sfo=1')
        self.assertNotIn('sender', cleaned)
        self.assertNotIn('invite', cleaned)

    def test_lookalikes_and_non_pins_are_rejected(self):
        for url in ('https://pinterest.com.evil.test/pin/123456/', 'https://evilpinterest.com/pin/123456/', 'https://www.pinterest.com.evil.test/pin/123456/',
                    'https://www.pinterest.com/someuser/board-name/', 'https://www.pinterest.com/pin/not-a-number/', 'https://www.pinterest.com/pin/12/',
                    'https://user:pw@www.pinterest.com/pin/123456/', 'https://www.pinterest.com:8443/pin/123456/', 'ftp://www.pinterest.com/pin/123456/',
                    'https://www.pinterest.com/pin/123456/../../etc', 'https://127.0.0.1/pin/123456/', 'https://pinterest.evil/pin/123456/x'):
            self.assertIsNone(app.clean_url(url), url)

    def test_media_hosts_are_limited_to_pinimg(self):
        for ok in ('https://i.pinimg.com/originals/a/b.jpg', 'https://v1.pinimg.com/videos/x.mp4', 'https://pinimg.com/x.jpg'):
            self.assertTrue(allowed_url(ok, 'pinterest'), ok)
        for bad in ('https://pinimg.com.evil.test/x.jpg', 'http://i.pinimg.com/x.jpg', 'https://evilpinimg.com/x.jpg', 'https://i.pinimg.com:444/x.jpg',
                    'https://scontent.cdninstagram.com/x.jpg', 'https://media.licdn.com/x.jpg', 'https://www.pinterest.com/pin/123456/'):
            self.assertFalse(allowed_url(bad, 'pinterest'), bad)
        self.assertFalse(allowed_url('https://i.pinimg.com/x.jpg', 'linkedin'))
        self.assertFalse(allowed_url('https://i.pinimg.com/x.jpg', 'instagram'))

    def test_pin_pages_are_only_fetched_from_pinterest_hosts(self):
        for ok in ('https://www.pinterest.com/pin/123456/', 'https://in.pinterest.com/pin/123456/', 'https://pinterest.co.uk/pin/123456/'):
            self.assertTrue(allowed_url(ok, 'pinterest', page=True), ok)
        for bad in ('https://pinterest.com.evil.test/pin/1/', 'https://i.pinimg.com/x', 'https://www.linkedin.com/posts/x', 'http://www.pinterest.com/pin/1/'):
            self.assertFalse(allowed_url(bad, 'pinterest', page=True), bad)


def redirect(location):
    response = MagicMock()
    response.is_redirect = True
    response.headers = {'Location': location}
    return response


class ShortLinkTests(unittest.TestCase):
    CHAIN = ['https://api.pinterest.com/url_shortener/1Llt9HRdp/redirect/',
             f'https://www.pinterest.com/pin/{PIN_ID}/sent/?invite_code=abc&sender=1113374476537736733&sfo=1']

    def test_pin_it_resolves_through_each_hop_to_a_clean_pin_url(self):
        responses = [redirect(location) for location in self.CHAIN]
        with patch('app.requests.get', side_effect=responses) as get:
            self.assertEqual(app.clean_url('https://pin.it/1Llt9HRdp'), PIN_URL)
        self.assertEqual([call.args[0] for call in get.call_args_list], ['https://pin.it/1Llt9HRdp', self.CHAIN[0]])
        self.assertTrue(all(call.kwargs['allow_redirects'] is False for call in get.call_args_list))
        for response in responses[:2]:
            response.close.assert_called()

    def test_short_link_variants(self):
        with patch('app.requests.get', side_effect=[redirect(location) for location in self.CHAIN]):
            self.assertEqual(app.clean_url('http://www.pin.it/1Llt9HRdp/'), PIN_URL)

    def test_unsafe_or_broken_redirects_are_refused(self):
        cases = (['https://evil.test/pin/123456/'], ['http://www.pinterest.com/pin/123456/'], ['https://127.0.0.1/pin/123456/'],
                 [self.CHAIN[0], 'https://evil.test/x'], ['https://user@www.pinterest.com/pin/123456/'], ['https://www.pinterest.com:444/pin/123456/'],
                 [self.CHAIN[0], 'https://www.pinterest.com/someuser/board/'])
        for hops in cases:
            with patch('app.requests.get', side_effect=[redirect(h) for h in hops]):
                self.assertIsNone(app.clean_url('https://pin.it/1Llt9HRdp'), hops)

    def test_redirect_loops_and_missing_locations_stop(self):
        with patch('app.requests.get', side_effect=[redirect('https://pin.it/loopAAAA') for _ in range(10)]) as get:
            self.assertIsNone(app.clean_url('https://pin.it/loopAAAA'))
        self.assertLessEqual(get.call_count, 5)
        not_redirect = MagicMock(is_redirect=False, headers={})
        with patch('app.requests.get', return_value=not_redirect):
            self.assertIsNone(app.clean_url('https://pin.it/1Llt9HRdp'))
        with patch('app.requests.get', side_effect=requests.ConnectionError('down')):
            self.assertIsNone(app.clean_url('https://pin.it/1Llt9HRdp'))

    def test_invalid_short_codes_do_not_make_requests(self):
        with patch('app.requests.get') as get:
            for url in ('https://pin.it/', 'https://pin.it/ab', 'https://pin.it/has space', 'https://pin.it/a/b', 'https://pin.it/' + 'x' * 70):
                self.assertIsNone(app.clean_url(url), url)
        get.assert_not_called()


class ExtractionTests(unittest.TestCase):
    def test_video_pin_uses_the_direct_mp4_and_ignores_the_cover_image(self):
        post = extract(page(posting(), video()))
        self.assertEqual(post['platform'], 'pinterest')
        self.assertEqual(post['uploader'], 'Some Creator')
        self.assertEqual(post['title'], 'Motion inspiration - Clip')
        self.assertEqual([a['kind'] for a in post['assets']], ['video'])
        self.assertEqual(post['assets'][0]['source'], MP4)
        self.assertEqual(post['assets'][0]['thumbnail'], THUMB)
        self.assertNotIn('ytdlp', post['assets'][0])

    def test_hls_content_url_is_replaced_by_the_same_videos_mp4_from_the_page(self):
        other = 'https://v1.pinimg.com/videos/iht/expMp4/11/22/33/' + 'f' * 32 + '_720w.mp4'
        smaller = MP4.replace('_720w', '_360w')
        extra = f'<script>{{"V_360P":{{"url":"{smaller}"}},"V_720P":{{"url":"{MP4}"}},"related":{{"url":"{other}"}}}}</script>'
        post = extract(page(posting(), video(content=HLS), extra=extra))
        self.assertEqual(post['assets'][0]['source'], MP4)
        self.assertNotIn('ytdlp', post['assets'][0])

    def test_highest_width_mp4_wins_and_other_videos_are_never_used(self):
        wide = MP4.replace('_720w', '_1080w')
        decoy = 'https://v1.pinimg.com/videos/iht/expMp4/11/22/33/' + 'e' * 32 + '_1080w.mp4'
        post = extract(page(posting(), video(content=HLS), extra=f'<p>{MP4} {wide} {decoy}</p>'))
        self.assertEqual(post['assets'][0]['source'], wide)

    def test_streaming_only_video_falls_back_to_yt_dlp(self):
        post = extract(page(posting(), video(content=HLS)))
        asset = post['assets'][0]
        self.assertEqual((asset['kind'], asset['source'], asset['ytdlp']), ('video', PIN_URL, True))
        self.assertEqual(asset['thumbnail'], THUMB)

    def test_video_on_an_untrusted_host_is_never_offered_directly(self):
        evil = 'https://evil.test/videos/clip.mp4'
        post = extract(page(posting(), video(content=evil, thumb='https://evil.test/t.jpg')))
        asset = post['assets'][0]
        self.assertTrue(asset['ytdlp'])
        self.assertIsNone(asset['thumbnail'])
        self.assertNotIn('evil.test', json.dumps(post))

    def test_image_pin_offers_the_original_with_a_reduced_fallback(self):
        post = extract(page(posting(image=ORIGINAL, headline='Modern Tennis Landing Page')))
        self.assertEqual([(a['kind'], a['source'], a['fallbacks']) for a in post['assets']], [('image', ORIGINAL, [REDUCED])])
        self.assertEqual(post['assets'][0]['thumbnail'], REDUCED)  # light preview; the download stays the original
        self.assertEqual(post['warnings'], [])

    def test_multi_image_pins_keep_order_and_derive_fallbacks(self):
        second = 'https://i.pinimg.com/originals/aa/bb/cc/aabbcc00112233445566778899aabbcc.gif'
        post = extract(page(posting(image=[ORIGINAL, {'url': second}, 'https://evil.test/x.jpg', 5])))
        self.assertEqual([a['source'] for a in post['assets']], [ORIGINAL, second])
        self.assertEqual([a['label'] for a in post['assets']], ['Image 1', 'Image 2'])
        self.assertEqual(post['assets'][1]['fallbacks'], ['https://i.pinimg.com/736x/aa/bb/cc/aabbcc00112233445566778899aabbcc.jpg'])

    def test_missing_markup_falls_back_to_the_reduced_social_image_with_a_warning(self):
        post = extract(page(og_image=REDUCED))
        self.assertEqual([a['source'] for a in post['assets']], [REDUCED])
        self.assertIn('reduced-size', ' '.join(post['warnings']))
        self.assertEqual(post['title'], 'Modern Tennis Landing Page')

    def test_empty_or_blocked_pages_raise_a_clear_error(self):
        for html in (b'<html><head><title></title></head><body>shell</body></html>', page(og_image='https://evil.test/x.jpg'),
                     page(posting(image='https://evil.test/x.png'), og_image='https://evil.test/y.jpg')):
            with patch('media_sources.fetch', return_value=(html, 'text/html')):
                with self.assertRaisesRegex(ValueError, 'No downloadable image or video was exposed'):
                    pinterest_post(PIN_URL)

    def test_titles_drop_keyword_tails_and_video_marker(self):
        self.assertEqual(extract(page(posting(headline='Cold Outreach | Cold email | Cold call'), video()))['title'], 'Cold Outreach')
        no_headline = posting(headline='')
        self.assertEqual(extract(page(no_headline, video(), og_title='Neon logo reveal [Video] | After effects, Motion'))['title'], 'Neon logo reveal')
        self.assertEqual(extract(page(None, None, og_title='', og_image=REDUCED))['title'], 'Pinterest pin')

    def test_malformed_json_ld_and_html_entities_do_not_break_extraction(self):
        html = page(posting(), video()).replace(b'</body>', b'<script type="application/ld+json">{not json</script></body>')
        self.assertEqual(extract(html)['assets'][0]['source'], MP4)
        entity = page(None, None, og_title='Tom &amp; Jerry &quot;Show&quot; | x')
        self.assertEqual(extract(entity)['title'], 'Tom & Jerry "Show"')

    def test_http_errors_become_friendly_messages(self):
        def failing(status):
            return requests.HTTPError(response=MagicMock(status_code=status))
        for status, text in ((404, 'could not find this pin'), (410, 'could not find this pin'), (403, 'limiting requests'), (429, 'limiting requests')):
            with patch('media_sources.time.sleep'), patch('media_sources.fetch', side_effect=failing(status)):
                with self.assertRaisesRegex(ValueError, text):
                    pinterest_post(PIN_URL)
        with patch('media_sources.fetch', side_effect=failing(500)) as fetch_mock:
            with self.assertRaises(requests.HTTPError):
                pinterest_post(PIN_URL)
        self.assertEqual(fetch_mock.call_count, 1)

    def test_one_throttled_response_is_retried_once(self):
        throttled = requests.HTTPError(response=MagicMock(status_code=429))
        with patch('media_sources.time.sleep') as pause, patch('media_sources.fetch', side_effect=[throttled, (page(posting(), video()), 'text/html')]) as fetch_mock:
            self.assertEqual(pinterest_post(PIN_URL)['assets'][0]['source'], MP4)
        self.assertEqual(fetch_mock.call_count, 2)
        pause.assert_called_once()

    def test_page_is_always_fetched_from_www_pinterest_com(self):
        self.assertEqual(app.clean_url('https://in.pinterest.com/pin/slug--' + PIN_ID + '/'), PIN_URL)


class AppIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app.sessions.clear()
        app.shutil.rmtree(app.DOWNLOAD_DIR, ignore_errors=True)
        self.post = dict(platform='pinterest', url=PIN_URL, uploader='Some Creator', title='Clip', warnings=[],
                         assets=[dict(kind='image', source=ORIGINAL, thumbnail=ORIGINAL, label='Image 1', fallbacks=[REDUCED])])

    def test_info_dispatches_pin_urls_to_the_pinterest_extractor(self):
        with patch('app.pinterest_post', return_value=self.post) as extractor, patch('app.linkedin_post') as linkedin, patch('app.instagram_post') as instagram:
            response = self.client.post('/api/info', json={'url': 'https://in.pinterest.com/pin/slug--' + PIN_ID + '/?x=1'})
        self.assertEqual(response.status_code, 200)
        extractor.assert_called_once_with(PIN_URL)
        linkedin.assert_not_called()
        instagram.assert_not_called()
        self.assertEqual(response.json['platform'], 'pinterest')
        self.assertNotIn('source', response.json['assets'][0])
        self.assertNotIn('fallbacks', response.json['assets'][0])

    def test_info_accepts_pin_it_links(self):
        chain = [redirect('https://api.pinterest.com/url_shortener/1Llt9HRdp/redirect/'), redirect(f'https://www.pinterest.com/pin/{PIN_ID}/sent/?sender=1')]
        with patch('app.requests.get', side_effect=chain), patch('app.pinterest_post', return_value=self.post) as extractor:
            response = self.client.post('/api/info', json={'url': 'https://pin.it/1Llt9HRdp'})
        self.assertEqual(response.status_code, 200)
        extractor.assert_called_once_with(PIN_URL)

    def test_info_reports_pinterest_errors_and_unsupported_links(self):
        with patch('app.pinterest_post', side_effect=ValueError('Pinterest could not find this pin.')):
            response = self.client.post('/api/info', json={'url': PIN_URL})
        self.assertEqual((response.status_code, response.json['error']), (502, 'Pinterest could not find this pin.'))
        board = self.client.post('/api/info', json={'url': 'https://www.pinterest.com/someone/a-board/'})
        self.assertEqual(board.status_code, 400)
        self.assertIn('Pinterest', board.json['error'])

    def test_download_falls_back_to_reduced_image_only_when_the_original_is_missing(self):
        token = app.remember(self.post)
        calls = []

        def fake_download(url, platform, path, limit):
            calls.append((url, platform))
            if url == ORIGINAL:
                raise requests.HTTPError(response=MagicMock(status_code=404))
            Path(path).write_bytes(b'\xff\xd8reduced')
            return 9, 'image/jpeg'

        with patch('app.download_to_path', side_effect=fake_download):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
            body = response.data
            response.close()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body, b'\xff\xd8reduced')
        self.assertEqual(calls, [(ORIGINAL, 'pinterest'), (REDUCED, 'pinterest')])
        self.assertIn('pinterest_Some_Creator_', response.headers['Content-Disposition'])
        self.assertIn(PIN_ID if PIN_ID in PIN_URL else '', response.headers['Content-Disposition'])
        self.assertEqual(os.listdir(app.DOWNLOAD_DIR), [])

    def test_missing_original_with_no_fallback_is_an_error_and_cleans_up(self):
        post = dict(self.post, assets=[dict(kind='image', source=ORIGINAL, thumbnail=None, label='Image 1')])
        token = app.remember(post)
        with patch('app.download_to_path', side_effect=requests.HTTPError(response=MagicMock(status_code=404))):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(os.listdir(app.DOWNLOAD_DIR), [])
        self.assertEqual(app.download_gate.active, 0)

    def test_size_limit_errors_do_not_trigger_the_fallback(self):
        token = app.remember(self.post)
        with patch('app.download_to_path', side_effect=ValueError('This file exceeds the download size limit.')) as download:
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(download.call_count, 1)

    def test_throttling_and_server_errors_do_not_trigger_image_fallback(self):
        token = app.remember(self.post)
        for status in (429, 500, 503):
            with self.subTest(status=status), patch('app.download_to_path', side_effect=requests.HTTPError(
                    response=MagicMock(status_code=status))) as downloader:
                response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
                self.assertEqual(response.status_code, 502)
                self.assertEqual(downloader.call_count, 1)
                self.assertEqual(app.download_gate.active, 0)
                self.assertEqual(os.listdir(app.DOWNLOAD_DIR), [])

    def test_video_pin_downloads_mp4_and_zip_mixes_are_ordered(self):
        post = dict(self.post, assets=[dict(kind='video', source=MP4, thumbnail=THUMB, label='Video')])
        token = app.remember(post)

        def fake_download(url, platform, path, limit):
            Path(path).write_bytes(b'\x00\x00\x00\x18ftypmp42')
            return 12, 'video/mp4'

        with patch('app.download_to_path', side_effect=fake_download):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
            data = response.data
            response.close()
        self.assertEqual(response.mimetype, 'video/mp4')
        self.assertIn('.mp4', response.headers['Content-Disposition'])
        self.assertEqual(data[4:8], b'ftyp')

    def test_yt_dlp_fallback_asset_downloads_with_a_muxing_format_and_no_playlist_options(self):
        post = dict(self.post, assets=[dict(kind='video', source=PIN_URL, ytdlp=True, thumbnail=None, label='Video')])
        token = app.remember(post)
        seen = {}

        class FakeYDL:
            def __init__(self, opts):
                seen.update(opts)
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download):
                seen['url'] = url
                Path(self.opts['outtmpl'].replace('%(id)s', 'pin').replace('%(ext)s', 'mp4')).write_bytes(b'\x00\x00\x00\x18ftypmp42')

        for has_ffmpeg, expected in ((True, 'bv*+ba/b'), (False, 'b')):
            seen.clear()
            with patch('app.yt_dlp.YoutubeDL', FakeYDL), patch.object(app, 'HAS_FFMPEG', has_ffmpeg):
                response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
                response.close()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(seen['format'], expected)
            self.assertEqual(seen['url'], PIN_URL)
            self.assertNotIn('playlist_items', seen)
            self.assertNotIn('cookiefile', seen)

    def test_zip_of_a_multi_image_pin_streams_in_order(self):
        second = 'https://i.pinimg.com/originals/aa/bb/cc/aabbcc00112233445566778899aabbcc.jpg'
        post = dict(self.post, assets=[dict(kind='image', source=ORIGINAL, label='Image 1'), dict(kind='image', source=second, label='Image 2')])
        token = app.remember(post)

        def fake_download(url, platform, path, limit):
            Path(path).write_bytes(url.encode())
            return len(url), 'image/png' if url.endswith('.png') else 'image/jpeg'

        import io
        import zipfile
        with patch('app.download_to_path', side_effect=fake_download):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': 'all'})
            data = response.data
            response.close()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), [f'pinterest_Some_Creator_{PIN_ID}_001.png', f'pinterest_Some_Creator_{PIN_ID}_002.jpg'])
            self.assertEqual(archive.read(archive.namelist()[0]), ORIGINAL.encode())


class PublicCopyTests(unittest.TestCase):
    def test_pages_mention_pinterest(self):
        client = app.app.test_client()
        with patch.object(app, 'PUBLIC_MODE', True):
            home = client.get('/').get_data(as_text=True)
            terms = client.get('/terms').get_data(as_text=True)
            privacy = client.get('/privacy').get_data(as_text=True)
        for text in (home, terms, privacy):
            self.assertIn('Pinterest', text)
        self.assertIn('pin.it', home)

    def test_docs_describe_pinterest_support(self):
        readme = (Path(__file__).parent / 'README.md').read_text(encoding='utf-8')
        self.assertIn('Pinterest', readme)
        self.assertIn('pin.it', readme)


if __name__ == '__main__':
    unittest.main()
