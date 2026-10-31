from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from . import views
from .context_processors import steam_promo
from .views import STEAM_EXPERIENCE

# The four pages that must never carry the Home pop up.
OTHER_PAGES = ['/about/', '/contact/', '/for-schools/', '/steam-experience/']

# Items shown in the redesigned "What's included" section.
EXPECTED_INCLUSIONS = [
    'Kits for use during the Build stage',
    'A kit to take home in the Innovate stage',
    'Snacks provided',
    'A showcase at the end of each level',
    'A certificate for each level completed',
    'Hands-on STEAM learning sessions',
    'Robotics and technology activities',
    'Practical creative projects',
    'Access to the M-Pass learning passport',
    'Facilitator guidance',
    'Project documentation and portfolio development',
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
        with mock.patch.dict(views.STEAM_EXPERIENCE, {'inclusions': []}):
            response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "What's included")
        self.assertNotContains(response, 'class="steam-inclusion-list"')

    def test_inclusions_filled_list_renders_all_items(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What's included")
        for item in EXPECTED_INCLUSIONS:
            self.assertContains(response, item)
        self.assertContains(response, 'fa-solid fa-circle-check', count=11)

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
        self.assertContains(response, "What's included")
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

    def test_break_marker_follows_the_stage_cards(self):
        html = self.client.get(self.url).content.decode()
        marker = html.index('steam-break-label')
        innovate = html.index('<h3>Innovate</h3>')
        self.assertLess(innovate, marker)

    def test_week_bar_has_nine_weeks(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'class="steam-week steam-week--', count=9)

    def test_full_journey_card_renders(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'The complete holiday journey')
        self.assertContains(response, 'UGX 1,100,000')

    def test_staged_payment_cards_render(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Programme details')
        self.assertContains(response, 'class="steam-payment-card', count=2)
        self.assertContains(response, 'How to pay')
        self.assertContains(response, "What's included")

    def test_payment_options_card_is_hidden_when_empty(self):
        with mock.patch.dict(STEAM_EXPERIENCE, {'payment_options': ''}):
            response = self.client.get(self.url)
        self.assertNotContains(response, 'class="steam-payment-card steam-payment-options"')

    def test_empty_stages_hide_the_journey_cards(self):
        with mock.patch.dict(STEAM_EXPERIENCE, {'stages': [], 'break': {}, 'full_journey': {}}):
            response = self.client.get(self.url)
        self.assertNotContains(response, 'steam-stage-card steam-stage-card--')
        self.assertNotContains(response, 'The learning journey: Discover, Build, Innovate')
        self.assertContains(response, 'Programme details')


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class SteamPopupHiddenTests(SimpleTestCase):
    """While the program is private the Home page carries no pop up."""

    def test_home_renders_without_a_database(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_no_popup_markup_when_not_public(self):
        response = self.client.get('/')
        self.assertNotContains(response, 'steam-popup')
        self.assertNotContains(response, '<dialog')
        self.assertNotContains(response, 'steam-popup-primary')

    def test_announcement_strip_hidden_when_not_public(self):
        response = self.client.get('/')
        self.assertNotContains(response, 'steam-strip')


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class SteamPopupTests(SimpleTestCase):
    """The Home pop up invites visitors to the STEAM Experience."""

    def test_home_shows_the_dialog(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<dialog class="steam-popup"')
        self.assertContains(response, 'id="steam-popup-title"')
        self.assertContains(response, 'Build it, code it, test it, and see your ideas come to life.')
        self.assertContains(response, 'Starts 16 November')
        self.assertContains(response, 'class="steam-popup-week ', count=9)
        self.assertContains(response, 'class="steam-popup-week-gap"', count=1)
        for stage in ('Discover', 'Build', 'Innovate'):
            self.assertContains(response, f'<span>{stage}</span>')
        self.assertContains(response, '16 November 2026 to 29 January 2027')
        self.assertContains(response, 'Ages 8 to 19')
        self.assertContains(response, 'Amreena Mall, Level 3, Room 304, Kyanja Ring Road')
        self.assertContains(response, 'Stages from UGX 300,000')
        self.assertContains(response, 'class="steam-popup-extra"', count=2)
        self.assertContains(response, 'class="steam-popup-price steam-popup-extra"')
        self.assertContains(response, 'Register your child')

    def test_shared_script_uses_per_visit_state(self):
        response = self.client.get('/')
        self.assertContains(response, "'steam-promo-visit'")
        self.assertNotContains(response, 'popupSeen')

    def test_register_button_links_to_holiday_join_form(self):
        response = self.client.get('/')
        html = response.content.decode()
        self.assertRegex(
            html,
            r'<a href="/join/\?programme=holiday" class="btn steam-popup-primary"'
            r'[^>]*data-umami-event="steam-popup-register"',
        )

    def test_shared_script_ignores_persistent_promo_storage(self):
        response = self.client.get('/')
        script = response.content.decode()
        self.assertNotIn('localStorage', script)
        self.assertNotRegex(script, r"""['"]steam-promo['"]""")
        self.assertIn("'steam-promo-visit'", script)

    def test_two_close_controls(self):
        response = self.client.get('/')
        # One on the pop up, one on the corner chip
        self.assertContains(response, 'aria-label="Close"', count=2)
        self.assertContains(response, 'Maybe later')
        self.assertContains(response, 'data-umami-event="steam-popup-close"', count=2)

    def test_corner_close_is_a_button_outside_the_link(self):
        response = self.client.get('/')
        html = response.content.decode()
        link_start = html.index('<a href="/steam-experience/" class="steam-chip-link"')
        link_end = html.index('</a>', link_start)
        close_start = html.index('<button type="button" class="steam-chip-close"', link_end)
        close_end = html.index('>', close_start)
        self.assertIn('aria-label="Close"', html[close_start:close_end])

    def test_other_pages_have_no_popup_markup(self):
        for url in OTHER_PAGES:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            # The shared promo script names the dialog with a selector,
            # so only the dialog markup itself is checked here.
            self.assertNotContains(response, '<dialog', msg_prefix=url)

    def test_announcement_strip_still_renders(self):
        response = self.client.get('/')
        self.assertContains(response, 'steam-strip')
        self.assertContains(response, 'Learn more')


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class SteamPromoHiddenTests(SimpleTestCase):
    """While the program is private no page carries any promo at all."""

    def test_no_promo_markup_on_home_about_or_schools(self):
        # The bare steam-chip name also belongs to the STEAM page meta
        # chips, so the corner reminder is checked by its own name.
        for url in ('/', '/about/', '/for-schools/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'steam-popup', msg_prefix=url)
            self.assertNotContains(response, 'steam-chip-corner', msg_prefix=url)
            self.assertNotContains(response, '<dialog', msg_prefix=url)


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class SteamChipTests(SimpleTestCase):
    """The corner chip follows the visitor around the public site."""

    def test_home_has_the_chip_and_the_dialog(self):
        response = self.client.get('/')
        self.assertContains(response, 'id="steam-chip-corner"')
        self.assertContains(response, 'data-umami-event="steam-chip-click"')
        self.assertContains(response, '<dialog class="steam-popup"')
        self.assertContains(response, 'Build it, code it, test it, and see your ideas come to life.')
        self.assertContains(response, 'class="steam-popup-week ', count=9)
        self.assertContains(response, 'class="steam-popup-week-gap"', count=1)
        for stage in ('Discover', 'Build', 'Innovate'):
            self.assertContains(response, f'<span>{stage}</span>')

    def test_about_and_schools_have_the_chip_but_no_dialog(self):
        for url in ('/about/', '/for-schools/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'id="steam-chip-corner"', msg_prefix=url)
            self.assertContains(response, 'data-umami-event="steam-chip-click"', msg_prefix=url)
            self.assertNotContains(response, '<dialog', msg_prefix=url)

    def test_excluded_pages_carry_no_promo(self):
        for url in ('/steam-experience/', '/contact/', '/privacy/',
                    '/share-your-story/', '/review/login/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'steam-chip-corner', msg_prefix=url)
            self.assertNotContains(response, 'steam-chip-click', msg_prefix=url)
            self.assertNotContains(response, 'steam-popup', msg_prefix=url)


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class SteamPromoContextTests(SimpleTestCase):
    """The context processor gates the chip by page and by setting."""

    def promo_for(self, path):
        request = RequestFactory().get(path)
        request.resolver_match = resolve(path)
        return steam_promo(request)

    def test_about_is_offered_the_promo(self):
        result = self.promo_for('/about/')
        self.assertTrue(result['steam_promo'])
        self.assertEqual(result['steam_start_date'], '2026-11-16')

    def test_excluded_pages_get_no_promo(self):
        for path in ('/steam-experience/', '/contact/', '/privacy/',
                     '/share-your-story/', '/review/login/'):
            self.assertFalse(self.promo_for(path)['steam_promo'], path)

    def test_admin_gets_no_promo(self):
        self.assertFalse(self.promo_for('/admin/')['steam_promo'])

    def test_private_program_turns_the_promo_off(self):
        with override_settings(STEAM_EXPERIENCE_PUBLIC=False):
            self.assertFalse(self.promo_for('/about/')['steam_promo'])

class BrandAssetsTests(SimpleTestCase):
    """The site header, footer and spotlight cards carry the proper brand assets."""

    def test_header_contains_mindset_logo_image(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        logo_start = html.index('class="logo"')
        logo_end = html.index('</a>', logo_start)
        logo_html = html[logo_start:logo_end]
        self.assertIn('<img', logo_html)
        self.assertIn('mindset-logo.png', logo_html)
        self.assertIn('alt="Mindset Coders"', logo_html)

    def test_footer_contains_white_mindset_logo_image(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'static/images/mindset-logo-white.png')
        self.assertContains(response, 'alt="Mindset Coders"')
        self.assertNotContains(
            response,
            '<div class="footer-brand">mindset<span class="logo-accent">&lt;/&gt;</span></div>',
        )

    def test_home_spotlight_card_contains_wro_logo(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        card_start = html.index('wro-spotlight')
        card_end = html.index('</section>', card_start)
        card_html = html[card_start:card_end]
        self.assertIn('<img', card_html)
        self.assertIn('wro-uganda-white.png', card_html)
        self.assertIn('alt="World Robot Olympiad Uganda"', card_html)

    def test_global_opportunities_spotlight_card_contains_wro_logo(self):
        response = self.client.get('/global-opportunities/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        card_start = html.index('wro-spotlight')
        card_end = html.index('</section>', card_start)
        card_html = html[card_start:card_end]
        self.assertIn('<img', card_html)
        self.assertIn('wro-uganda-white.png', card_html)
        self.assertIn('alt="World Robot Olympiad Uganda"', card_html)
