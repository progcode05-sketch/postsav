import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parent


class ProductionServerTests(unittest.TestCase):
    def test_wsgi_entry_point_exports_flask_app(self):
        import app
        import wsgi
        self.assertIs(wsgi.application, app.app)

    def test_gunicorn_defaults_fit_free_instance(self):
        with patch.dict(os.environ, {}, clear=True):
            config = runpy.run_path(str(ROOT / 'gunicorn.conf.py'))
        self.assertEqual(config['bind'], '0.0.0.0:10000')
        self.assertEqual(config['workers'], 1)
        self.assertEqual(config['worker_class'], 'gthread')
        self.assertEqual(config['threads'], 4)
        self.assertEqual(config['timeout'], 300)
        self.assertFalse(config['preload_app'])

    def test_gunicorn_uses_host_environment(self):
        environment = {'PORT': '12345', 'WEB_THREADS': '2', 'REQUEST_TIMEOUT': '90'}
        with patch.dict(os.environ, environment, clear=True):
            config = runpy.run_path(str(ROOT / 'gunicorn.conf.py'))
        self.assertEqual(config['bind'], '0.0.0.0:12345')
        self.assertEqual(config['threads'], 2)
        self.assertEqual(config['timeout'], 90)

    def test_procfile_uses_production_entry_point(self):
        command = (ROOT / 'Procfile').read_text(encoding='utf-8').strip()
        self.assertEqual(command, 'web: gunicorn --config gunicorn.conf.py wsgi:application')

    def test_docker_image_is_non_root_and_includes_ffmpeg(self):
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('FROM python:3.12.14-slim-bookworm', dockerfile)
        self.assertIn('ffmpeg', dockerfile)
        self.assertIn('USER downloader', dockerfile)
        self.assertIn('CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]', dockerfile)
        self.assertLess(dockerfile.index('USER downloader'), dockerfile.index('CMD ['))

    def test_docker_context_excludes_credentials(self):
        ignored = set((ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines())
        self.assertIn('cookies.txt', ignored)
        self.assertIn('*.cookies.txt', ignored)
        self.assertIn('.env', ignored)
        self.assertIn('.venv', ignored)


    def test_render_blueprint_is_free_and_wired_to_key_value(self):
        blueprint = (ROOT / 'render.yaml').read_text(encoding='utf-8')
        self.assertEqual(blueprint.count('plan: free'), 2)
        self.assertNotIn('plan: starter', blueprint)
        self.assertIn('healthCheckPath: /healthz', blueprint)
        self.assertIn('property: connectionString', blueprint)
        self.assertIn('CLIENT_IP_HEADER', blueprint)
        self.assertIn('ipAllowList: []', blueprint)
        self.assertEqual(blueprint.count('region: oregon'), 2)


if __name__ == '__main__':
    unittest.main()
