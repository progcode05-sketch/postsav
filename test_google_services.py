"""Optional Google integrations must fail closed and match public disclosures."""
import os
import unittest
from unittest.mock import patch

import app
import seo


class GoogleServicesTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'GA_MEASUREMENT_ID': '', 'ADSENSE_PUBLISHER_ID': '', 'ADSENSE_ENABLED': '', 'SITE_URL': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        seo._page_cache.clear()
        self.client = app.app.test_client()

    def page(self, path='/'):
        return self.client.get(path).get_data(as_text=True)

    def test_disabled_by_default(self):
        with patch.object(app, 'PUBLIC_MODE', True):
            body = self.page()
            self.assertNotIn('privacy.js', body)
            self.assertNotIn('adsbygoogle.js', body)
            self.assertEqual(self.client.get('/ads.txt').status_code, 404)

    def test_invalid_identifiers_never_reach_html(self):
        with patch.dict(os.environ, {'GA_MEASUREMENT_ID': 'G-<script>', 'ADSENSE_PUBLISHER_ID': 'ca-pub-invalid', 'ADSENSE_ENABLED': '1'}), patch.object(app, 'PUBLIC_MODE', True):
            self.assertEqual(seo.google_services(), dict(measurement_id='', publisher_id='', ads_enabled=False))
            self.assertNotIn('adsbygoogle.js', self.page())

    def test_analytics_configuration_invalidates_cached_page(self):
        with patch.object(app, 'PUBLIC_MODE', True):
            self.assertNotIn('privacy.js', self.page())
            with patch.dict(os.environ, {'GA_MEASUREMENT_ID': 'G-ABCD123456'}):
                body = self.page()
                self.assertIn('privacy.js', body)
                self.assertIn('data-measurement-id="G-ABCD123456"', body)
                self.assertIn('Reject analytics', body)
                self.assertNotIn('googletagmanager.com', body)
                self.assertIn('only after you choose Allow analytics', self.page('/privacy'))

    def test_publisher_verification_and_ads_txt_without_serving_ads(self):
        with patch.dict(os.environ, {'ADSENSE_PUBLISHER_ID': 'ca-pub-1234567890123456'}), patch.object(app, 'PUBLIC_MODE', True):
            body = self.page()
            self.assertIn('google-adsense-account', body)
            self.assertNotIn('adsbygoogle.js', body)
            response = self.client.get('/ads.txt')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(as_text=True), 'google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n')

    def test_ads_require_explicit_enable_and_privacy_disclosure(self):
        with patch.dict(os.environ, {'ADSENSE_PUBLISHER_ID': 'ca-pub-1234567890123456', 'ADSENSE_ENABLED': '1'}), patch.object(app, 'PUBLIC_MODE', True):
            self.assertIn('adsbygoogle.js?client=ca-pub-1234567890123456', self.page())
            self.assertIn('uses Google AdSense', self.page('/privacy'))
            self.assertNotIn('adsbygoogle.js', self.page('/missing'))

    def test_no_google_tags_in_local_mode_or_error_pages(self):
        with patch.dict(os.environ, {'GA_MEASUREMENT_ID': 'G-ABCD123456', 'ADSENSE_PUBLISHER_ID': 'ca-pub-1234567890123456', 'ADSENSE_ENABLED': '1'}):
            with patch.object(app, 'PUBLIC_MODE', False):
                self.assertNotIn('privacy.js', self.page())
                self.assertNotIn('adsbygoogle.js', self.page())
                self.assertEqual(self.client.get('/ads.txt').status_code, 404)
            with patch.object(app, 'PUBLIC_MODE', True):
                self.assertNotIn('privacy.js', self.page('/missing'))


if __name__ == '__main__':
    unittest.main()
