import re
from django.test import SimpleTestCase

LINE_1 = 'M-Pass is the Mindset STEAM Learning Passport, helping learners document their projects, showcase their work, and track their growth in practical STEAM competencies.'
LINE_2 = "It combines a learner portfolio with evidence-based competency tracking, making each learner's progress visible and giving them a record of what they can do."


class MPassCopyTests(SimpleTestCase):
    """M-Pass replaces Mindset Learn across the public pages."""

    def test_pages_do_not_contain_words_mindset_learn(self):
        pages = [
            '/',
            '/about/',
            '/for-schools/',
            '/partners/',
            '/global-opportunities/',
            '/steam-experience/',
        ]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f'{url} failed to render')
            html = response.content.decode('utf-8')
            # Check for the words 'Mindset Learn' (case-insensitive word match)
            self.assertIsNone(
                re.search(r'\bMindset\s+Learn\b', html, re.I),
                f'Found "Mindset Learn" in {url}',
            )

    def test_mpass_two_lines_appear_word_for_word_on_home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn(LINE_1, html)
        self.assertIn(LINE_2, html)

    def test_home_join_buttons_point_to_the_join_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        # All Join buttons on Home should point to /join/
        join_matches = re.findall(r'<a\b[^>]*href="(/join/|{% url \'join\' %})"[^>]*>\s*Join\s*</a>', html)
        self.assertGreaterEqual(len(join_matches), 3)
