import io
import os
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace

import app
from media_sources import allowed_url, linkedin_post, instagram_post, fetch


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app.sessions.clear()
        app.shutil.rmtree(app.DOWNLOAD_DIR, ignore_errors=True)
        self.post = dict(platform='linkedin', url='https://www.linkedin.com/posts/test-activity-1234-abcd', uploader='Someone', title='Post', warnings=[], assets=[dict(kind='image', source='https://media.licdn.com/one'), dict(kind='image', source='https://media.licdn.com/two')])

    def test_url_validation(self):
        self.assertEqual(app.clean_url('https://www.instagram.com/user/reel/ABC/?igsh=x'), 'https://www.instagram.com/reel/ABC/')
        self.assertEqual(app.clean_url('https://www.linkedin.com/feed/update/urn%3Ali%3Aactivity%3A123/?x=1'), 'https://www.linkedin.com/feed/update/urn:li:activity:123')
        for url in ('https://linkedin.com.evil.test/posts/x-activity-123-abcd', 'https://www.instagram.com/reel/ABC/extra', 'https://user@linkedin.com/posts/x-activity-123-abcd', 'https://127.0.0.1/', [], 'https://linkedin.com:999/posts/x-activity-123-abcd'):
            self.assertIsNone(app.clean_url(url))
        self.assertFalse(allowed_url('https://media.licdn.com.evil.test/file', 'linkedin'))
        self.assertFalse(allowed_url('http://media.licdn.com/file', 'linkedin'))

    def test_linkedin_short_url_resolution(self):
        response = MagicMock()
        response.is_redirect = True
        response.headers = {'Location': 'https://www.linkedin.com/posts/person_topic-activity-1234-abcd/?utm_source=share'}
        with patch('app.requests.get', return_value=response):
            self.assertEqual(app.clean_url('https://lnkd.in/p/AbCd_123'), 'https://www.linkedin.com/posts/person_topic-activity-1234-abcd')
        response.close.assert_called_once()

    def test_linkedin_short_url_rejects_unsafe_redirect(self):
        response = MagicMock()
        response.is_redirect = True
        response.headers = {'Location': 'https://127.0.0.1/private'}
        with patch('app.requests.get', return_value=response):
            self.assertIsNone(app.clean_url('https://lnkd.in/p/AbCd_123'))

    def test_public_ugc_post_short_link_video_is_resolved_and_extracted(self):
        target = 'https://www.linkedin.com/posts/keagan-stokoe_topic-ugcPost-7510392940888756226-U5BC'
        redirect = MagicMock(is_redirect=True)
        redirect.headers = {'Location': target + '/?utm_source=share'}
        page = b'''<article class="main-feed-activity-card" data-activity-urn="urn:li:ugcPost:7510392940888756226"><video data-sources='[{"type":"video/mp4","src":"https://media.licdn.com/video.mp4","data-bitrate":100}]'></video></article>'''
        with patch('app.requests.get', return_value=redirect), patch('media_sources.fetch', return_value=(page, 'text/html')):
            result = self.client.post('/api/info', json={'url': 'https://lnkd.in/p/ejQkjf9E', 'ack': True})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['url'], target)
        self.assertEqual(result.json['assets'][0]['kind'], 'video')
        self.assertEqual(app.get_session(result.json['session'])['assets'][0]['source'], 'https://media.licdn.com/video.mp4')

    def test_linkedin_signup_page_reports_access_restriction_without_session(self):
        page = b'<title>Sign Up | LinkedIn</title><form action="/signup/api/cors/createAccount"></form>'
        with patch('media_sources.fetch', return_value=(page, 'text/html')):
            result = self.client.post('/api/info', json={'url': self.post['url'], 'ack': True})
        self.assertEqual(result.status_code, 502)
        self.assertIn('requires sign-in', result.json['error'])
        self.assertIn('original file', result.json['error'])
        self.assertEqual(app.sessions, {})

    def test_info_hides_download_sources(self):
        with patch('app.linkedin_post', return_value=self.post):
            r = self.client.post('/api/info', json={'url': self.post['url']})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('source', r.json['assets'][0])
        self.assertEqual(len(r.json['assets']), 2)
        self.assertIn(r.json['session'], app.sessions)
        self.assertEqual(self.client.post('/api/info', json=[]).status_code, 400)

    def test_individual_and_zip(self):
        token = app.remember(self.post)
        def fake_asset(_post, _asset, index, workdir):
            path = os.path.join(workdir, f'fixture_{index}.jpg')
            Path(path).write_bytes(b'image' + bytes([index]))
            return path, f'slide_{index+1}.jpg', 'image/jpeg'
        with patch('app.asset_file', side_effect=fake_asset):
            single = self.client.get('/api/download', query_string={'session': token, 'asset': '1'})
            self.assertEqual(single.data, b'image\x01')
            single.close()
            self.assertFalse(os.listdir(app.DOWNLOAD_DIR))
            bundle = self.client.get('/api/download', query_string={'session': token, 'asset': 'all'})
            with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
                self.assertEqual(archive.namelist(), ['slide_1.jpg', 'slide_2.jpg'])
                self.assertEqual(archive.read('slide_2.jpg'), b'image\x01')
            bundle.close()
            self.assertFalse(os.listdir(app.DOWNLOAD_DIR))
        self.assertEqual(self.client.get('/api/download', query_string={'session': token, 'asset': '-1'}).status_code, 400)
        self.assertEqual(self.client.get('/api/download?session=missing').status_code, 410)
        app.sessions[token] = (0, self.post)
        self.assertEqual(self.client.get('/api/download', query_string={'session': token}).status_code, 410)

    def test_parser_excludes_unrelated_images(self):
        html = b'''<meta property="og:title" content="Someone on LinkedIn"><article class="main-feed-activity-card" data-activity-urn="urn:li:activity:1234"><img src="https://media.licdn.com/dms/image/profile-displayphoto/x"><img data-delayed-url="https://media.licdn.com/dms/image/feedshare-shrink_1280/a"><img src="https://media.licdn.com/dms/image/feedshare-shrink_1280/b"></article><img src="https://media.licdn.com/dms/image/feedshare-shrink_1280/related">'''
        with patch('media_sources.fetch', return_value=(html, 'text/html')):
            post = linkedin_post(self.post['url'])
        self.assertEqual(len(post['assets']), 2)
        self.assertTrue(post['assets'][1]['source'].endswith('/b'))

    def test_download_error_is_inline_json(self):
        token = app.remember(self.post)
        with patch('app.asset_file', side_effect=ValueError('This file exceeds the download size limit.')):
            r = self.client.get('/api/download', query_string={'session': token})
        self.assertEqual(r.status_code, 502)
        self.assertIn('size limit', r.json['error'])

    def test_media_download_streams_chunks_to_disk(self):
        from media_sources import download_to_path
        response = MagicMock()
        response.__enter__.return_value = response
        response.is_redirect = False
        response.headers = {'Content-Type': 'image/jpeg', 'Content-Length': '6'}
        response.iter_content.return_value = [b'abc', b'def']
        with app.tempfile.TemporaryDirectory() as directory, patch('media_sources.requests.get', return_value=response):
            path = os.path.join(directory, 'media')
            size, mime = download_to_path('https://media.licdn.com/file', 'linkedin', path, 10)
            self.assertEqual((size, mime), (6, 'image/jpeg'))
            self.assertEqual(Path(path).read_bytes(), b'abcdef')

    def test_media_download_removes_partial_oversize_file(self):
        from media_sources import download_to_path
        response = MagicMock()
        response.__enter__.return_value = response
        response.is_redirect = False
        response.headers = {'Content-Type': 'video/mp4'}
        response.iter_content.return_value = [b'1234', b'5678']
        with app.tempfile.TemporaryDirectory() as directory, patch('media_sources.requests.get', return_value=response):
            path = os.path.join(directory, 'media')
            with self.assertRaisesRegex(ValueError, 'size limit'):
                download_to_path('https://media.licdn.com/file', 'linkedin', path, 6)
            self.assertFalse(os.path.exists(path))

    def test_instagram_mixed_carousel(self):
        post = SimpleNamespace(typename='GraphSidecar', caption='Mixed post', owner_username='author', get_sidecar_nodes=lambda: [SimpleNamespace(is_video=False, display_url='https://x.cdninstagram.com/photo.jpg'), SimpleNamespace(is_video=True, video_url='https://x.cdninstagram.com/video.mp4', display_url='https://x.cdninstagram.com/thumb.jpg')])
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.side_effect = ValueError('No videos')
        with patch('yt_dlp.YoutubeDL', return_value=ydl), patch('instaloader.Instaloader'), patch('instaloader.Post.from_shortcode', return_value=post):
            data = instagram_post('https://www.instagram.com/p/ABC/', lambda: {})
        self.assertEqual([a['kind'] for a in data['assets']], ['image', 'video'])
        self.assertTrue(data['assets'][1]['source'].endswith('video.mp4'))

    def test_document_manifests_and_pdf_gate(self):
        import json
        doc = dict(totalPageCount=2, manifestUrl='https://media.licdn.com/manifest')
        html = '<article class="main-feed-activity-card" data-activity-urn="urn:li:activity:1234"><iframe data-native-document-config=\'' + json.dumps({'doc': doc}) + '\'></iframe></article>'
        manifest = dict(scanRequiredForDownload=True, transcribedDocumentUrl='https://media.licdn.com/gated.pdf', perResolutions=[dict(width=100, imageManifestUrl='https://media.licdn.com/small'), dict(width=1000, imageManifestUrl='https://media.licdn.com/large')])
        pages = dict(pages=['https://media.licdn.com/slide1', 'https://media.licdn.com/slide2'])
        with patch('media_sources.fetch', side_effect=[(html.encode(), 'text/html'), (json.dumps(manifest).encode(), 'application/json'), (json.dumps(pages).encode(), 'application/json')]) as mocked:
            data = linkedin_post(self.post['url'])
        self.assertEqual(len(data['assets']), 2)
        self.assertEqual(mocked.call_args_list[2].args[0], 'https://media.licdn.com/large')
        self.assertTrue(all(a['kind'] == 'image' for a in data['assets']))
        self.assertTrue(data['warnings'])

    def test_redirect_cannot_leave_cdn(self):
        response = MagicMock()
        response.__enter__.return_value.is_redirect = True
        response.__enter__.return_value.headers = {'Location': 'https://127.0.0.1/private'}
        with patch('media_sources.requests.get', return_value=response) as get:
            with self.assertRaises(ValueError):
                fetch('https://media.licdn.com/file', 'linkedin')
        self.assertEqual(get.call_count, 1)

    def test_hidden_linkedin_images_and_high_res_paths(self):
        import json
        urls = [f'https://media.licdn.com/dms/image/feedshare-image-high-res/{i}' for i in range(8)]
        record = {'@type': 'SocialMediaPosting', '@id': self.post['url'], 'image': [{'url': u} for u in urls]}
        html = '<script type="application/ld+json">'+json.dumps(record)+'</script><article class="main-feed-activity-card" data-activity-urn="urn:li:activity:1234">'+''.join(f'<img src="{u}">' for u in urls[:5])+'</article>'
        with patch('media_sources.fetch', return_value=(html.encode(), 'text/html')):
            data = linkedin_post(self.post['url'])
        self.assertEqual([a['source'] for a in data['assets']], urls)

    def test_huge_and_unicode_attachment_ids(self):
        token = app.remember(self.post)
        for asset in ('9' * 5000, '\u0660', '-1', '1.5', 'allx'):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': asset})
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json)

    def test_large_request_is_json(self):
        response = self.client.post('/api/info', json={'url': 'x' * 9000})
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.json)

    def test_empty_extraction_does_not_create_session(self):
        self.post['assets'] = []
        with patch('app.linkedin_post', return_value=self.post):
            response = self.client.post('/api/info', json={'url': self.post['url']})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(app.sessions)

    def test_wrong_linkedin_post_rejected(self):
        html = b'<article class="main-feed-activity-card" data-activity-urn="urn:li:activity:9999"><img src="https://media.licdn.com/dms/image/feedshare-shrink_800/x"></article>'
        with patch('media_sources.fetch', return_value=(html, 'text/html')):
            with self.assertRaisesRegex(ValueError, 'different post'):
                linkedin_post(self.post['url'])

    def test_instagram_video_reuses_extracted_url(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = dict(url='https://x.cdninstagram.com/video.mp4', ext='mp4', uploader='author')
        with patch('yt_dlp.YoutubeDL', return_value=ydl):
            data = instagram_post('https://www.instagram.com/reel/ABC/', lambda: {})
        self.assertNotIn('entry', data['assets'][0])

    def test_post_filenames_do_not_collide(self):
        second = dict(self.post, url='https://www.linkedin.com/posts/test-activity-5555-abcd')
        self.assertNotEqual(app.post_name(self.post), app.post_name(second))

    def test_new_linkedin_image_paths_are_native_only(self):
        html = b'<article class="main-feed-activity-card" data-activity-urn="urn:li:activity:1234"><div class="feed-images-content"><img src="https://media.licdn.com/dms/image/image-shrink_800/a"></div><div class="feed-article-content"><img src="https://media.licdn.com/dms/image/image-shrink_800/article"></div></article>'
        with patch('media_sources.fetch', return_value=(html, 'text/html')):
            data = linkedin_post(self.post['url'])
        self.assertEqual(len(data['assets']), 1)
        self.assertTrue(data['assets'][0]['source'].endswith('/a'))


if __name__ == '__main__':
    unittest.main()
