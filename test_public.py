"""Offline tests for the public-beta controls: limits, Redis sessions, health, legal pages, cookie refusal."""
import json
import os
import runpy
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from limits import DownloadGate, RateLimiter

ROOT = Path(__file__).parent
POST = dict(platform='linkedin', url='https://www.linkedin.com/posts/test-activity-1234-abcd', uploader='Someone', title='Post', warnings=[],
            assets=[dict(kind='image', source='https://media.licdn.com/one'), dict(kind='image', source='https://media.licdn.com/two')])


class FakeRedis:
    def __init__(self):
        self.data, self.ttls = {}, {}

    def set(self, key, value, ex=None):
        self.data[key], self.ttls[key] = value, ex

    def get(self, key):
        return self.data.get(key)

    def ping(self):
        return True


class BrokenRedis:
    def set(self, *args, **kwargs):
        raise ConnectionError('down')

    get = ping = set


def fake_asset(_post, _asset, index, workdir):
    path = os.path.join(workdir, f'fixture_{index}.jpg')
    Path(path).write_bytes(b'image' + bytes([index]))
    return path, f'slide_{index + 1}.jpg', 'image/jpeg'


class Base(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app.sessions.clear()
        app.rate_limiter = RateLimiter()
        app.download_gate = DownloadGate()
        app.shutil.rmtree(app.DOWNLOAD_DIR, ignore_errors=True)


class LimiterTests(unittest.TestCase):
    def test_sliding_window(self):
        now = [0.0]
        limiter = RateLimiter(clock=lambda: now[0])
        self.assertTrue(all(limiter.check('a', 3)[0] for _ in range(3)))
        allowed, retry = limiter.check('a', 3)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)
        self.assertTrue(limiter.check('b', 3)[0])
        now[0] = 61
        self.assertTrue(limiter.check('a', 3)[0])
        self.assertTrue(limiter.check('a', 0)[0])

    def test_gate_limits_total_and_per_client_and_releases_once(self):
        gate = DownloadGate()
        first = gate.acquire('a', 2, 1)
        self.assertIsNone(gate.acquire('a', 2, 1))
        second = gate.acquire('b', 2, 1)
        self.assertIsNone(gate.acquire('c', 2, 1))
        self.assertEqual(gate.active, 2)
        first()
        first()
        self.assertEqual(gate.active, 1)
        self.assertIsNotNone(gate.acquire('c', 2, 1))
        second()


class PublicApiTests(Base):
    def test_rate_limit_returns_429_with_retry_after(self):
        with patch.object(app, 'RATE_INFO_PER_MIN', 2), patch('app.linkedin_post', return_value=POST):
            codes = [self.client.post('/api/info', json={'url': POST['url']}).status_code for _ in range(3)]
            blocked = self.client.post('/api/info', json={'url': POST['url']})
        self.assertEqual(codes, [200, 200, 429])
        self.assertIn('Retry-After', blocked.headers)
        self.assertIn('wait', blocked.json['error'])

    def test_ownership_acknowledgment_required_in_public_mode(self):
        with patch.object(app, 'PUBLIC_MODE', True), patch('app.linkedin_post', return_value=POST):
            missing = self.client.post('/api/info', json={'url': POST['url']})
            false = self.client.post('/api/info', json={'url': POST['url'], 'ack': 'true'})
            accepted = self.client.post('/api/info', json={'url': POST['url'], 'ack': True})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(false.status_code, 400)
        self.assertIn('permission', missing.json['error'])
        self.assertEqual(accepted.status_code, 200)

    def test_acknowledgment_not_required_locally(self):
        with patch.object(app, 'PUBLIC_MODE', False), patch('app.linkedin_post', return_value=POST):
            self.assertEqual(self.client.post('/api/info', json={'url': POST['url']}).status_code, 200)

    def test_concurrency_cap_returns_503_and_slot_is_released_after_response(self):
        token = app.remember(POST)
        with patch('app.asset_file', side_effect=fake_asset), patch.object(app, 'MAX_DOWNLOADS_PER_CLIENT', 1):
            first = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(app.download_gate.active, 1)
            blocked = self.client.get('/api/download', query_string={'session': token, 'asset': '1'})
            self.assertEqual(blocked.status_code, 503)
            self.assertIn('Retry-After', blocked.headers)
            first.close()
            self.assertEqual(app.download_gate.active, 0)
            self.assertEqual(self.client.get('/api/download', query_string={'session': token, 'asset': '1'}).status_code, 200)

    def test_unread_response_still_cleans_job_and_slot(self):
        token = app.remember(POST)
        with patch('app.asset_file', side_effect=fake_asset):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'}, buffered=False)
            self.assertEqual(len(os.listdir(app.DOWNLOAD_DIR)), 1)
            response.close()
        self.assertEqual(os.listdir(app.DOWNLOAD_DIR), [])
        self.assertEqual(app.download_gate.active, 0)

    def test_failed_download_releases_slot(self):
        token = app.remember(POST)
        with patch('app.asset_file', side_effect=RuntimeError('boom')):
            self.assertEqual(self.client.get('/api/download', query_string={'session': token, 'asset': '0'}).status_code, 502)
        self.assertEqual(app.download_gate.active, 0)
        self.assertEqual(os.listdir(app.DOWNLOAD_DIR), [])

    def test_disk_budget_refuses_new_jobs(self):
        token = app.remember(POST)
        os.makedirs(app.DOWNLOAD_DIR, exist_ok=True)
        with patch.object(app, 'DISK_BUDGET', -1), patch('app.asset_file', side_effect=fake_asset):
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(app.download_gate.active, 0)

    def test_malformed_session_token_is_expired(self):
        self.assertEqual(self.client.get('/api/download', query_string={'session': 'short', 'asset': '0'}).status_code, 410)


class CookieRefusalTests(Base):
    def test_public_mode_never_uses_cookies(self):
        with patch.object(app, 'PUBLIC_MODE', True), patch.object(app, 'BROWSER', 'chrome'), patch('app.os.path.exists', return_value=True):
            opts = app.ydl_opts()
        self.assertNotIn('cookiefile', opts)
        self.assertNotIn('cookiesfrombrowser', opts)

    def test_local_mode_still_supports_cookies(self):
        with patch.object(app, 'PUBLIC_MODE', False), patch('app.os.path.exists', return_value=True):
            self.assertIn('cookiefile', app.ydl_opts())
        with patch.object(app, 'PUBLIC_MODE', False), patch.object(app, 'BROWSER', 'firefox'), patch('app.os.path.exists', return_value=False):
            self.assertEqual(app.ydl_opts()['cookiesfrombrowser'], ('firefox',))

    def test_public_error_text_does_not_ask_for_cookies(self):
        with patch.object(app, 'PUBLIC_MODE', True):
            text = app.friendly_error(RuntimeError('login required'))
        self.assertNotIn('cookie', text.lower())


class RedisSessionTests(Base):
    def test_sessions_round_trip_through_redis_with_ttl(self):
        fake = FakeRedis()
        with patch.object(app, 'REDIS_URL', 'redis://x'), patch.object(app, '_redis_client', fake):
            token = app.remember(POST)
            self.assertEqual(app.get_session(token), POST)
        self.assertNotIn(token, app.sessions)
        (key, ttl), = fake.ttls.items()
        self.assertEqual(ttl, app.SESSION_TTL)
        self.assertEqual(json.loads(fake.data[key])['assets'][0]['kind'], 'image')

    def test_redis_outage_falls_back_to_memory(self):
        with patch.object(app, 'REDIS_URL', 'redis://x'), patch.object(app, '_redis_client', BrokenRedis()):
            token = app.remember(POST)
            self.assertIn(token, app.sessions)
            self.assertEqual(app.get_session(token), POST)
            self.assertIsNone(app.get_session('A' * 32))

    def test_download_works_with_redis_sessions(self):
        fake = FakeRedis()
        with patch.object(app, 'REDIS_URL', 'redis://x'), patch.object(app, '_redis_client', fake), patch('app.asset_file', side_effect=fake_asset):
            token = app.remember(POST)
            response = self.client.get('/api/download', query_string={'session': token, 'asset': '0'})
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_expired_memory_session_is_missing(self):
        token = 'T' * 32
        app.sessions[token] = (time.monotonic() - 1, POST)
        self.assertIsNone(app.get_session(token))


class HealthAndLegalTests(Base):
    def test_liveness(self):
        response = self.client.get('/healthz')
        self.assertEqual((response.status_code, response.json), (200, {'status': 'ok'}))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_readiness_reports_checks_and_degrades(self):
        ok = self.client.get('/readyz')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json['checks']['storage'])
        with patch.object(app, 'REDIS_URL', 'redis://x'), patch.object(app, '_redis_client', BrokenRedis()):
            bad = self.client.get('/readyz')
        self.assertEqual(bad.status_code, 503)
        self.assertFalse(bad.json['checks']['redis'])
        with patch.object(app, 'MIN_FREE_DISK', 1 << 60):
            self.assertEqual(self.client.get('/readyz').status_code, 503)

    def test_health_checks_are_not_rate_limited(self):
        with patch.object(app, 'RATE_INFO_PER_MIN', 1), patch.object(app, 'RATE_DOWNLOAD_PER_MIN', 1):
            self.assertTrue(all(self.client.get('/healthz').status_code == 200 for _ in range(5)))

    def test_legal_pages_render_without_inventing_operator(self):
        for slug in ('terms', 'privacy', 'copyright', 'contact'):
            response = self.client.get(f'/{slug}')
            self.assertEqual(response.status_code, 200, slug)
            self.assertIn('has not been configured', response.get_data(as_text=True))
        self.assertEqual(self.client.get('/nonsense').status_code, 404)

    def test_legal_pages_show_configured_contact(self):
        with patch.object(app, 'OPERATOR_NAME', 'Example Ops'), patch.object(app, 'CONTACT_EMAIL', 'legal@example.test'):
            body = self.client.get('/contact').get_data(as_text=True)
            self.assertIn('mailto:legal@example.test', body)
            self.assertIn('Example Ops', body)
            self.assertNotIn('has not been configured', body)
            self.assertTrue(self.client.get('/readyz').json['legal_contact_configured'])

    def test_home_page_modes(self):
        with patch.object(app, 'PUBLIC_MODE', True):
            body = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="ack"', body)
        self.assertIn('href="/privacy"', body)
        self.assertNotIn('Runs locally', body)
        with patch.object(app, 'PUBLIC_MODE', False):
            body = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('id="ack"', body)
        self.assertIn('Runs locally', body)


class ClientAddressTests(Base):
    def test_client_ip_header_is_used_when_configured_and_valid(self):
        with patch.object(app, 'CLIENT_IP_HEADER', 'CF-Connecting-IP'), app.app.test_request_context('/', headers={'CF-Connecting-IP': '203.0.113.9'}, environ_base={'REMOTE_ADDR': '10.0.0.1'}):
            self.assertEqual(app.client_ip(), '203.0.113.9')
        with patch.object(app, 'CLIENT_IP_HEADER', 'CF-Connecting-IP'), app.app.test_request_context('/', headers={'CF-Connecting-IP': 'not-an-ip'}, environ_base={'REMOTE_ADDR': '10.0.0.1'}):
            self.assertEqual(app.client_ip(), '10.0.0.1')
        with patch.object(app, 'CLIENT_IP_HEADER', ''), app.app.test_request_context('/', headers={'CF-Connecting-IP': '203.0.113.9'}, environ_base={'REMOTE_ADDR': '10.0.0.1'}):
            self.assertEqual(app.client_ip(), '10.0.0.1')

    def test_rate_limit_is_per_forwarded_client(self):
        with patch.object(app, 'CLIENT_IP_HEADER', 'CF-Connecting-IP'), patch.object(app, 'RATE_INFO_PER_MIN', 1), patch('app.linkedin_post', return_value=POST):
            send = lambda ip: self.client.post('/api/info', json={'url': POST['url']}, headers={'CF-Connecting-IP': ip}).status_code
            self.assertEqual([send('198.51.100.1'), send('198.51.100.2'), send('198.51.100.1')], [200, 200, 429])


class CleanupTests(Base):
    def test_stale_sweep_removes_only_old_jobs(self):
        os.makedirs(app.DOWNLOAD_DIR, exist_ok=True)
        old, fresh = Path(app.DOWNLOAD_DIR, 'job_old'), Path(app.DOWNLOAD_DIR, 'job_new')
        for directory in (old, fresh):
            directory.mkdir()
            (directory / 'file').write_bytes(b'x')
        past = time.time() - app.STALE_DOWNLOAD_AGE - 60
        os.utime(old, (past, past))
        app.cleanup_stale_downloads()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_background_cleanup_starts_once_and_sweeps_at_startup(self):
        calls = []
        with patch.object(app, '_background_started', False), patch('app.cleanup_stale_downloads', side_effect=lambda: calls.append(1)), patch('app.time.sleep', side_effect=SystemExit):
            app.start_background_cleanup()
            app.start_background_cleanup()
            deadline = time.time() + 2
            while not calls and time.time() < deadline:
                time.sleep(0.01)
        self.assertEqual(calls, [1])


class DeploymentConfigTests(unittest.TestCase):
    def test_access_log_omits_query_strings(self):
        with patch.dict(os.environ, {}, clear=True):
            config = runpy.run_path(str(ROOT / 'gunicorn.conf.py'))
        self.assertIn('%(U)s', config['access_log_format'])
        self.assertNotIn('%(r)s', config['access_log_format'])
        self.assertNotIn('%(q)s', config['access_log_format'])

    def test_docker_image_runs_in_public_mode_with_new_modules(self):
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('PUBLIC_MODE=1', dockerfile)
        self.assertIn('limits.py', dockerfile)
        self.assertIn('redis', (ROOT / 'requirements.txt').read_text(encoding='utf-8'))

    def test_public_mode_environment_defaults(self):
        code = "import app; print(app.PUBLIC_MODE, app.RATE_INFO_PER_MIN, app.MAX_DOWNLOADS_PER_CLIENT)"
        import subprocess, sys
        env = {**os.environ, 'PUBLIC_MODE': '1'}
        env.pop('RATE_INFO_PER_MIN', None)
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ['True', '10', '1'])


if __name__ == '__main__':
    unittest.main()
