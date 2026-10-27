from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import views
from .views import STEAM_EXPERIENCE

# The five items the price section shows under "What is included".
EXPECTED_INCLUSIONS = [
    'Kits for use during the Build stage',
    'A kit to take home in the Innovate stage',
    'Snacks provided',
    'A showcase at the end of each level',
    'A certificate for each level completed',
]

# Fragments from the unconfirmed, bracketed sentences on the privacy page.
# They are kept in {% comment %} blocks in the template, so none of these
# may ever appear in the rendered HTML.
UNCONFIRMED_SNIPPETS = [
    'permission comes from a parent or guardian for anyone under 18',
    'this does not follow you from site to site',
    'does not collect your name or email',
    "we ask for a parent or guardian's consent first",
    'only the people who need the information to run the programme can see it',
    'our reports use learner ID numbers instead of names',
    'Retention period to be confirmed',
    'messages and stories are stored securely with our hosting and database providers',
    'emails to our team go through an email service',
]


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class SteamExperiencePageTests(SimpleTestCase):
    """The STEAM Experience page needs no database to render."""

    def get_page(self):
        return self.client.get('/steam-experience/')

    def test_page_renders_without_a_database(self):
        # SimpleTestCase fails any test that touches the database, so a
        # successful 200 here proves the page renders without one.
        response = self.get_page()
        self.assertEqual(response.status_code, 200)

    def test_inclusions_empty_list_renders_nothing(self):
        # With an empty list the section must not appear at all.
        with mock.patch.dict(views.STEAM_EXPERIENCE, {'inclusions': []}):
            response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'What is included')
        self.assertNotContains(response, '<ul class="tick-list-compact">')

    def test_inclusions_filled_list_renders_five_items(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What is included')
        for item in EXPECTED_INCLUSIONS:
            self.assertContains(response, item)
        # Exactly five tick marks are rendered for the five inclusions.
        self.assertContains(response, 'fa-solid fa-check', count=5)

    def test_noindex_still_applies_when_not_public(self):
        response = self.get_page()
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertContains(response, 'noindex, nofollow', status_code=200)


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class SteamExperiencePublicTests(SimpleTestCase):
    """When the page is public it is indexable again."""

    def test_noindex_header_absent_when_public(self):
        response = self.client.get('/steam-experience/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header('X-Robots-Tag'))
        self.assertNotContains(response, 'noindex', status_code=200)

    def test_inclusions_still_render_when_public(self):
        response = self.client.get('/steam-experience/')
        self.assertContains(response, 'What is included')
        self.assertContains(response, EXPECTED_INCLUSIONS[0])


class PrivacyPageTests(SimpleTestCase):
    """The privacy page needs no database to render."""

    def get_page(self):
        return self.client.get('/privacy/')

    def test_page_renders_without_a_database(self):
        # SimpleTestCase fails any test that touches the database, so a
        # successful 200 here proves the page renders without one.
        response = self.get_page()
        self.assertEqual(response.status_code, 200)

    def test_page_appears_in_the_sitemap(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/privacy/')

    def test_footer_links_to_the_privacy_page(self):
        # The footer lives on every page, so check the link on the home page.
        response = self.client.get('/')
        self.assertContains(response, 'Privacy')

    def test_no_unconfirmed_text_is_rendered(self):
        # Every bracketed, unconfirmed sentence must stay in a comment block
        # and never reach the rendered page.
        response = self.get_page()
        self.assertEqual(response.status_code, 200)
        for fragment in UNCONFIRMED_SNIPPETS:
            self.assertNotContains(response, fragment)

    def test_confirmed_copy_is_rendered(self):
        response = self.get_page()
        self.assertContains(response, 'What this website collects')
        self.assertContains(response, "Children's information")
        self.assertContains(response, 'How long we keep information')
        self.assertContains(response, 'Who looks after your information')
        self.assertContains(response, 'Questions')


class SteamJourneyTests(SimpleTestCase):
    url = '/steam-experience/'

    def test_three_stage_cards_render(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'steam-stage-card steam-stage-card--', count=3)

    def test_break_marker_sits_between_build_and_innovate(self):
        html = self.client.get(self.url).content.decode()
        build = html.index('<h3>Build</h3>')
        marker = html.index('steam-break-label')
        innovate = html.index('<h3>Innovate</h3>')
        self.assertLess(build, marker)
        self.assertLess(marker, innovate)

    def test_week_bar_has_nine_weeks(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="steam-week steam-week--', count=9)

    def test_full_journey_card_renders(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'The complete holiday journey')
        self.assertContains(response, 'UGX 1,100,000')

    def test_empty_stages_fall_back_to_old_sections(self):
        with mock.patch.dict(STEAM_EXPERIENCE, {'stages': [], 'break': {}, 'full_journey': {}}):
            response = self.client.get(self.url)
        self.assertNotContains(response, 'steam-stage-card steam-stage-card--')
        self.assertContains(response, 'Dates and schedule')
