from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import views

# The four items the price section shows under "What is included".
EXPECTED_INCLUSIONS = [
    'Kits for use during the Build stage',
    'A kit to take home in the Innovate stage',
    'Snacks provided',
    'A showcase at the end of each level',
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
        self.assertNotContains(response, EXPECTED_INCLUSIONS[0])

    def test_inclusions_filled_list_renders_four_items(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What is included')
        for item in EXPECTED_INCLUSIONS:
            self.assertContains(response, item)
        # Exactly four tick marks are rendered for the four inclusions.
        self.assertContains(response, 'fa-solid fa-check', count=4)

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
