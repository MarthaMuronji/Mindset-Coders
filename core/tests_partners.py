import re
from unittest import mock

from django.test import SimpleTestCase

PARTNER_LOGOS = [
    ('camden-education-trust.png', 'Camden Education Trust'),
    ('google.png', 'Google'),
    ('innovation-village.png', 'Innovation Village'),
    ('microbit.png', 'Micro:bit Educational Foundation'),
    ('mtn.png', 'MTN'),
    ('national-schools-championship.png', 'National Schools Championship'),
    ('scratch-foundation.png', 'Scratch Foundation'),
    ('technovation-girls-uganda.png', 'Technovation Girls Uganda'),
]


class PartnerLogoTests(SimpleTestCase):
    def _strip(self, html, start_marker):
        start = html.index(start_marker)
        end = html.index('</section>', start)
        return html[start:end]

    def test_logo_files_exist_and_are_within_size_limit(self):
        from pathlib import Path

        from django.conf import settings

        partners_dir = Path(settings.BASE_DIR) / 'static' / 'images' / 'partners'
        for name, _alt in PARTNER_LOGOS:
            with self.subTest(name=name):
                path = partners_dir / name
                self.assertTrue(path.exists(), f'{path.name} is missing')
                self.assertLess(path.stat().st_size, 25_000, f'{path.name} exceeds 25 KB')

    def test_partners_page_shows_each_logo_once_with_alt_text(self):
        response = self.client.get('/partners/')
        self.assertEqual(response.status_code, 200)
        strip = self._strip(response.content.decode(), '<div class="partner-logo-grid">')
        for name, _alt in PARTNER_LOGOS:
            with self.subTest(name=name):
                self.assertEqual(strip.count(f'/static/images/partners/{name}'), 1)
        alts = re.findall(
            r'<img src="/static/images/partners/[a-z0-9-]+\.png" alt="([^"]*)"',
            strip,
        )
        self.assertEqual(len(alts), len(PARTNER_LOGOS))
        for alt in alts:
            self.assertTrue(alt.strip(), 'each partner logo must have alt text')

    def test_no_partner_logo_is_a_link(self):
        response = self.client.get('/partners/')
        strip = self._strip(response.content.decode(), '<div class="partner-logo-grid">')
        self.assertEqual(re.findall(r'<a\b', strip), [])
        self.assertEqual(strip.count('<img '), len(PARTNER_LOGOS))

    def test_home_strip_uses_logos_and_keeps_text_names(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        strip = self._strip(response.content.decode(), '<div class="trusted-logos">')
        self.assertContains(response, 'images/partners/google.png')
        self.assertContains(response, 'images/partners/mtn.png')
        self.assertIn('Mastercard Foundation', strip)
        self.assertIn('Stanbic Bank', strip)
        self.assertIn('WRO Global', strip)
        self.assertNotIn('>Google</span>', strip)
        self.assertNotIn('>MTN Uganda</span>', strip)

    def test_pages_render_when_a_logo_file_is_missing(self):
        with mock.patch(
            'django.contrib.staticfiles.storage.staticfiles_storage.url',
            side_effect=lambda name: f'/static/{name}',
        ):
            for url in ('/', '/partners/'):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Partner')
