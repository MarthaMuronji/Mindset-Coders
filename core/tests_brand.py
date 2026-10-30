import re
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TEMPLATE_PATH = ROOT / 'templates'


def relative_luminance(color):
    channels = [
        int(color[index:index + 2], 16) / 255
        for index in (1, 3, 5)
    ]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return (
        0.2126 * linear[0]
        + 0.7152 * linear[1]
        + 0.0722 * linear[2]
    )


def contrast_ratio(first, second):
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


class BrandPaletteTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = CSS_PATH.read_text(encoding='utf-8')
        cls.templates = '\n'.join(
            path.read_text(encoding='utf-8')
            for path in TEMPLATE_PATH.rglob('*.html')
        )

    def token(self, name):
        match = re.search(
            rf'--{re.escape(name)}:\s*(#[0-9A-Fa-f]{{6}})\s*;',
            self.css,
        )
        self.assertIsNotNone(match, f'Missing color token --{name}')
        return match.group(1)

    def test_brand_tokens_use_the_confirmed_palette(self):
        self.assertEqual(self.token('navy').upper(), '#034D62')
        self.assertEqual(self.token('navy-dark').upper(), '#023746')
        self.assertEqual(self.token('green').upper(), '#32CD32')
        self.assertEqual(self.token('green-dark').upper(), '#176B17')
        self.assertEqual(self.token('green-light').upper(), '#E8F8E8')

        self.assertIn('--green-btn: var(--navy);', self.css)
        self.assertIn('--green-btn-hover: var(--navy-dark);', self.css)
        self.assertIn('<meta name="theme-color" content="#034D62">', self.templates)

    def test_legacy_brand_colors_and_rgb_values_are_removed(self):
        old_colors = (
            '#16324F', '#0F2438', '#2FA84F', '#248F41', '#1E7A38',
            '#18622D', '#E8F7EA', '#0B3818', '#7CCB8F', '#CDEAD2',
            '#D7E8DB', '#D4EADC', '#F0F9F2',
        )
        content = self.css + '\n' + self.templates
        for color in old_colors:
            with self.subTest(color=color):
                self.assertNotIn(color.lower(), content.lower())

        legacy_rgb = (
            r'22\s*,\s*50\s*,\s*79',
            r'15\s*,\s*36\s*,\s*56',
            r'47\s*,\s*168\s*,\s*79',
            r'30\s*,\s*122\s*,\s*56',
        )
        for rgb in legacy_rgb:
            with self.subTest(rgb=rgb):
                self.assertNotRegex(
                    content,
                    rf'rgba?\(\s*{rgb}\s*,',
                )

    def test_text_button_and_link_contrast_meets_wcag_thresholds(self):
        navy = self.token('navy')
        navy_dark = self.token('navy-dark')
        green = self.token('green')
        green_dark = self.token('green-dark')
        green_light = self.token('green-light')

        self.assertGreaterEqual(contrast_ratio(navy, '#FFFFFF'), 4.5)
        self.assertGreaterEqual(contrast_ratio('#FFFFFF', navy), 4.5)
        self.assertGreaterEqual(contrast_ratio(green_dark, '#FFFFFF'), 4.5)
        self.assertGreaterEqual(contrast_ratio(navy, green_light), 4.5)
        self.assertGreaterEqual(contrast_ratio(green, navy), 3)
        self.assertGreaterEqual(contrast_ratio(navy_dark, green), 4.5)
        self.assertGreaterEqual(contrast_ratio(green, navy_dark), 3)

        self.assertRegex(
            self.css,
            r'\.btn-primary\s*\{\s*background:\s*var\(--navy\);\s*color:\s*var\(--white\);',
        )
        self.assertRegex(
            self.css,
            r'\.nav-links a:hover\s*\{\s*color:\s*var\(--green-dark\);',
        )
        self.assertRegex(
            self.css,
            r'\.footer-links a:hover\s*\{\s*color:\s*var\(--white\);',
        )
        self.assertRegex(
            self.css,
            r'\.steam-strip a\s*\{\s*color:\s*var\(--white\);',
        )
        self.assertNotRegex(
            self.css,
            r'background:\s*var\(--green\);\s*color:\s*var\(--white\);',
        )

    def test_focus_outlines_remain_visible(self):
        self.assertRegex(
            self.css,
            r'\.btn:focus-visible,[\s\S]*?outline:\s*2px solid var\(--navy\);',
        )

    def test_footer_uses_the_white_logo_image_instead_of_the_text_wordmark(self):
        footer_match = re.search(
            r'<footer class="site-footer">([\s\S]*?)</footer>',
            self.templates,
        )
        self.assertIsNotNone(footer_match)
        footer = footer_match.group(1)

        self.assertIn(
            '<img src="{% static \'images/mindset-logo-white.png\' %}" '
            'alt="Mindset Coders" width="320" height="160" loading="lazy">',
            footer,
        )
        self.assertNotIn('mindset<span class="logo-accent">', footer)
        self.assertRegex(
            self.css,
            r'\.footer-brand img\s*\{[^}]*width:\s*160px;[^}]*height:\s*80px;'
            r'[^}]*max-width:\s*100%;[^}]*margin:\s*0 auto;',
        )
