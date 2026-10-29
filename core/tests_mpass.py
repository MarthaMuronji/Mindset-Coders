from django.test import SimpleTestCase


class MPassMenuTests(SimpleTestCase):
    """The main navigation menu links to M-Pass instead of Mindset Learn."""

    def get_navbar_html(self, path='/'):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        start = html.index('<ul class="nav-links">')
        end = html.index('</ul>', start)
        return html[start:end]

    def test_menu_contains_mpass_link(self):
        nav_html = self.get_navbar_html()
        self.assertIn('https://mpass.mindsetlearn.org/auth', nav_html)
        self.assertIn('>M-Pass</a>', nav_html)

    def test_mpass_link_opens_in_new_tab(self):
        nav_html = self.get_navbar_html()
        # Find the M-Pass link tag specifically
        mpass_idx = nav_html.index('https://mpass.mindsetlearn.org/auth')
        tag_start = nav_html.rfind('<a ', 0, mpass_idx)
        tag_end = nav_html.index('>', mpass_idx)
        tag = nav_html[tag_start:tag_end]

        self.assertIn('target="_blank"', tag)
        self.assertIn('rel="noopener noreferrer"', tag)

    def test_mpass_link_carries_umami_event(self):
        nav_html = self.get_navbar_html('/')
        self.assertIn('data-umami-event="go-mpass"', nav_html)
        self.assertIn('data-umami-event-from="home"', nav_html)

    def test_menu_does_not_contain_mindset_learn_link(self):
        nav_html = self.get_navbar_html()
        self.assertNotIn('/mindset-learn/', nav_html)
        self.assertNotIn('Mindset Learn</a>', nav_html)

    def test_login_link_is_absent_and_mpass_link_remains(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('https://www.mindsetlearn.org/', html)
        self.assertNotRegex(html, r'<[^>]+\bclass="[^"]*\bbtn-login\b')
        self.assertIn('href="https://mpass.mindsetlearn.org/auth"', html)

    def test_mindset_learn_redirects_to_join(self):
        response = self.client.get('/mindset-learn/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/join/')
