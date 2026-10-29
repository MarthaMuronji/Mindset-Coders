"""Tests for the STEAM Experience pay buttons (Prompt D).

The STEAM Experience page and the join-thanks page both need a database for
their URL resolvers only (Django's URL framework needs app registry). All
page content comes from the STEAM_EXPERIENCE dictionary, so every class here
uses SimpleTestCase and needs no database.
"""

import re
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import views

JOIN_LINK = '/join/?programme=holiday'
THANKS_URL = '/join/thanks/'

# The hero, the contact section and the sticky bar at the bottom of the page.
REGISTER_BUTTONS = 3

# The four KaCyberPay payment links, in order. Each entry carries the
# stage key the confirmation page matches against, so these tests never
# depend on the dictionary in views.
PAY_LINKS = [
    {
        'key': 'discover',
        'label': 'Discover, 2 weeks',
        'amount_text': 'UGX 300,000',
        'url': 'https://kacyberpay.com/pay/f47mjrdxje',
    },
    {
        'key': 'build',
        'label': 'Build, 3 weeks',
        'amount_text': 'UGX 400,000',
        'url': 'https://kacyberpay.com/pay/ys7azaf25a',
    },
    {
        'key': 'innovate',
        'label': 'Innovate, 4 weeks',
        'amount_text': 'UGX 500,000',
        'url': 'https://kacyberpay.com/pay/gjuffbu4je',
    },
    {
        'key': 'full',
        'label': 'Full journey, paid upfront',
        'amount_text': 'UGX 1,100,000',
        'url': 'https://kacyberpay.com/pay/hc6sn7yqxq',
    },
]


def register_anchors(html, href):
    """Every Register link on the page that points at href."""
    pattern = r'<a\b[^>]*href="%s"[^>]*>.*?</a>' % re.escape(href)
    return [
        anchor for anchor in re.findall(pattern, html, re.S)
        if 'Register your child' in anchor
    ]


class SteamPageTestCase(SimpleTestCase):
    """Renders the STEAM Experience page with optional dictionary overrides."""

    def get_page(self, **overrides):
        # The view reads the dictionary while it renders, so patching it here
        # changes what the page shows without touching the database.
        with mock.patch.dict(views.STEAM_EXPERIENCE, overrides):
            return self.client.get('/steam-experience/')


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class RegisterLinkTests(SteamPageTestCase):
    """Each Register button opens the join route with ?programme=holiday."""

    def test_page_still_renders_without_a_database(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)

    def test_every_register_button_points_at_the_join_route(self):
        response = self.get_page()
        html = response.content.decode()
        anchors = register_anchors(html, JOIN_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)

    def test_kacyberpay_does_not_appear_on_the_page_by_default(self):
        # Without payment_links in the dict, nothing from KaCyberPay shows up.
        response = self.get_page(payment_links=[])
        html = response.content.decode()
        self.assertNotIn('kacyberpay', html.lower())

    def test_every_register_button_sends_the_register_click_event(self):
        response = self.get_page()
        html = response.content.decode()
        anchors = register_anchors(html, JOIN_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        for anchor in anchors:
            self.assertIn('data-umami-event="register-click"', anchor)
            self.assertIn('data-umami-event-from="steam-experience"', anchor)

    def test_merchant_pay_does_not_appear(self):
        response = self.get_page()
        html = response.content.decode()
        self.assertNotContains(response, 'Merchant Pay')
        self.assertIsNone(re.search(r'merchant\s+pay', html, re.I))
        self.assertContains(
            response, 'Pay online by Mobile Money. You can also pay in cash.'
        )


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class PaymentNoteTests(SteamPageTestCase):
    """One short line under the Register button, only when it is filled in."""

    NOTE = 'A short note for the test'

    @staticmethod
    def hero(html):
        match = re.search(
            r'<section class="about-hero steam-hero.*?</section>', html, re.S
        )
        assert match is not None, 'the hero section did not render'
        return match.group()

    def test_empty_note_renders_nothing_extra(self):
        response = self.get_page(payment_note=None)
        html = response.content.decode()
        self.assertNotIn('steam-payment-note', html)
        # The button is still the last thing in the hero section.
        self.assertRegex(self.hero(html), r'</a></p>\s*</section>$')

    def test_filled_note_shows_one_line_under_the_button(self):
        response = self.get_page(payment_note=self.NOTE)
        html = response.content.decode()
        self.assertRegex(
            self.hero(html),
            r'</a></p>\s*<p class="steam-payment-note">%s</p>'
            % re.escape(self.NOTE),
        )
        # One line, in one place, and nowhere else on the page.
        self.assertEqual(html.count('steam-payment-note'), 1)


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class PaymentLinkButtonTests(SteamPageTestCase):
    """Payment links are reserved for the confirmation page."""

    def test_payment_addresses_do_not_appear_on_the_steam_page(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        for link in PAY_LINKS:
            self.assertNotIn(link['url'], html)

    def test_pay_buttons_carry_pay_click_event(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        for link in PAY_LINKS:
            pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
            matches = re.findall(pattern, html)
            for anchor_open in matches:
                self.assertIn('data-umami-event="pay-click"', anchor_open)

    def test_pay_buttons_carry_level_property(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        for link in PAY_LINKS:
            pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
            matches = re.findall(pattern, html)
            for anchor_open in matches:
                self.assertIn(
                    'data-umami-event-level="%s"' % link['label'],
                    anchor_open,
                )

    def test_no_sdk_script_on_page(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        # No KaCyberPay SDK script address should appear anywhere.
        self.assertNotIn('sdk.js', html.lower())
        self.assertNotIn('kacyberpay.com/sdk', html.lower())

    def test_payment_link_data_and_payment_intro_setting(self):
        links = views.STEAM_EXPERIENCE['payment_links']
        self.assertEqual(len(links), 4)
        actual = {
            entry['key']: (entry['url'], entry['amount_text'])
            for entry in links
        }
        self.assertEqual(actual, {
            'discover': ('https://kacyberpay.com/pay/f47mjrdxje', 'UGX 300,000'),
            'build': ('https://kacyberpay.com/pay/ys7azaf25a', 'UGX 400,000'),
            'innovate': ('https://kacyberpay.com/pay/gjuffbu4je', 'UGX 500,000'),
            'full': ('https://kacyberpay.com/pay/hc6sn7yqxq', 'UGX 1,100,000'),
        })
        self.assertNotIn('payment_intro', views.STEAM_EXPERIENCE)

    def test_empty_payment_links_renders_no_pay_block(self):
        response = self.get_page(payment_links=[])
        html = response.content.decode()
        self.assertNotIn('steam-pay-buttons', html)
        self.assertNotIn('kacyberpay', html.lower())

    def test_payment_intro_text_does_not_appear_on_steam_page(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        intro = 'Register your child first, then pay with the option you chose.'
        self.assertNotIn(intro, html)


@override_settings(STEAM_PAYMENTS_ENABLED=True)
class JoinThanksPaymentTests(SimpleTestCase):
    """The join-thanks confirmation page after a saved registration.

    The page shows one pay button for the stage the parent picked, and
    only while STEAM_PAYMENTS_ENABLED is True. In every other case it is
    the plain thank you page, which still offers a way back to the form.
    """

    PLAIN_TEXT = (
        'We have received your registration. Our team will get in touch '
        'with you about the next steps.'
    )

    def _get_thanks(self, programme='', stage='', links=None, enabled=True):
        payment_links = PAY_LINKS if links is None else links
        with mock.patch.dict(views.STEAM_EXPERIENCE, {'payment_links': payment_links}):
            with self.settings(STEAM_PAYMENTS_ENABLED=enabled):
                return self.client.get(
                    THANKS_URL + '?programme=%s&stage=%s' % (programme, stage)
                )

    def assert_plain_page(self, response):
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.PLAIN_TEXT, html)
        self.assertNotIn('kacyberpay', html.lower())
        self.assertNotIn('join-pay', html)
        self.assertNotIn('Fee:', html)
        # Even the plain page offers a way back to the form
        self.assertContains(response, 'Register another child')
        self.assertContains(response, 'href="/join/?programme=holiday"')

    def test_holiday_with_a_valid_stage_shows_the_confirmation(self):
        response = self._get_thanks(programme='holiday', stage='build')
        html = response.content.decode()
        self.assertIn('Thank you', html)
        self.assertIn(
            'We have received your registration for the Holiday STEAM '
            'Experience, Build (3 weeks).',
            html,
        )
        self.assertIn('Fee: UGX 400,000', html)
        self.assertIn(
            'Your registration is confirmed once we receive your payment.',
            html,
        )
        self.assertIn(
            'Registering more than one child? Contact our team to arrange '
            'your 10% sibling discount before making payment.',
            html,
        )

    def test_the_confirmation_carries_the_contact_line(self):
        response = self._get_thanks(programme='holiday', stage='discover')
        self.assertContains(response, 'Questions? Call')
        self.assertContains(response, 'href="tel:+256752064343"')
        self.assertContains(response, 'href="https://wa.me/256752064343"')
        self.assertContains(response, '+256 752 064343')
        self.assertContains(
            response, 'href="mailto:info@mindset-group.org"'
        )

    def test_the_pay_button_matches_the_stage(self):
        response = self._get_thanks(programme='holiday', stage='innovate')
        html = response.content.decode()
        link = PAY_LINKS[2]
        self.assertIn('class="join-pay"', html)
        self.assertIn(
            'Pay %s with Mobile Money' % link['amount_text'], html
        )
        pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
        matches = re.findall(pattern, html)
        self.assertTrue(matches, 'No pay anchor for %s' % link['url'])
        for anchor_open in matches:
            self.assertIn('target="_blank"', anchor_open)
            self.assertIn('rel="noopener noreferrer"', anchor_open)
            self.assertIn('data-umami-event="pay-click"', anchor_open)
            self.assertIn(
                'data-umami-event-level="%s"' % link['label'], anchor_open
            )
        # Only the chosen stage is offered, never the other three
        for other in PAY_LINKS:
            if other is not link:
                self.assertNotIn(other['url'], html)

    def test_the_refund_policy_link_is_a_plain_path(self):
        response = self._get_thanks(programme='holiday', stage='discover')
        self.assertContains(response, 'href="/refund-policy/"')
        self.assertContains(
            response, 'Read our refund and cancellation policy'
        )

    def test_switching_the_setting_off_shows_the_plain_page(self):
        response = self._get_thanks(
            programme='holiday', stage='discover', enabled=False
        )
        self.assert_plain_page(response)

    def test_a_wrong_stage_shows_the_plain_page(self):
        response = self._get_thanks(programme='holiday', stage='bronze')
        self.assert_plain_page(response)

    def test_no_stage_shows_the_plain_page(self):
        response = self._get_thanks(programme='holiday')
        self.assert_plain_page(response)

    def test_another_programme_shows_the_plain_page_even_with_a_stage(self):
        response = self._get_thanks(programme='weekend', stage='discover')
        self.assert_plain_page(response)

    def test_no_programme_shows_the_plain_page(self):
        response = self._get_thanks()
        self.assert_plain_page(response)

    def test_empty_payment_links_shows_the_plain_page(self):
        response = self._get_thanks(
            programme='holiday', stage='discover', links=[]
        )
        self.assert_plain_page(response)

    def test_links_without_a_matching_key_show_the_plain_page(self):
        # The dictionary before the team fills in the keys: same links,
        # but nothing to match the stage against
        keyless = [
            {name: value for name, value in link.items() if name != 'key'}
            for link in PAY_LINKS
        ]
        response = self._get_thanks(
            programme='holiday', stage='discover', links=keyless
        )
        self.assert_plain_page(response)
