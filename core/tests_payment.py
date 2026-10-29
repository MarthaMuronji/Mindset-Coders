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

# The four KaCyberPay payment links, in order.
PAY_LINKS = [
    {
        'label': 'Discover, 2 weeks',
        'amount_text': 'UGX 300,000',
        'url': 'https://kacyberpay.com/pay/f47mjrdxje',
    },
    {
        'label': 'Build, 3 weeks',
        'amount_text': 'UGX 400,000',
        'url': 'https://kacyberpay.com/pay/ys7azaf25a',
    },
    {
        'label': 'Innovate, 4 weeks',
        'amount_text': 'UGX 500,000',
        'url': 'https://kacyberpay.com/pay/gjuffbu4je',
    },
    {
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
        if 'Register your interest' in anchor
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
        self.assertContains(response, 'Pay online by Mobile Money')


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
    """The four pay buttons appear on the STEAM Experience page."""

    def test_all_four_pay_buttons_render(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        for link in PAY_LINKS:
            self.assertIn(link['url'], html)
            self.assertIn(link['label'], html)
            self.assertIn(link['amount_text'], html)

    def test_pay_buttons_open_in_new_tab(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        # Find each pay button anchor and check target and rel.
        for link in PAY_LINKS:
            pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
            matches = re.findall(pattern, html)
            self.assertTrue(matches, 'No anchor found for %s' % link['url'])
            for anchor_open in matches:
                self.assertIn('target="_blank"', anchor_open)
                self.assertIn('rel="noopener noreferrer"', anchor_open)

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

    def test_each_amount_appears_once_on_the_steam_page(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        # Each amount_text must appear exactly once in the pay buttons block.
        # (The price field may repeat them in another section, so we count
        # occurrences in the pay buttons section only.)
        pay_section_match = re.search(
            r'class="steam-pay-buttons".*?</div>', html, re.S
        )
        self.assertIsNotNone(pay_section_match, 'steam-pay-buttons div not found')
        pay_section = pay_section_match.group()
        for link in PAY_LINKS:
            self.assertEqual(
                pay_section.count(link['amount_text']),
                1,
                '%s appears more than once in the pay buttons block' % link['amount_text'],
            )

    def test_empty_payment_links_renders_no_pay_block(self):
        response = self.get_page(payment_links=[])
        html = response.content.decode()
        self.assertNotIn('steam-pay-buttons', html)
        self.assertNotIn('kacyberpay', html.lower())

    def test_payment_intro_appears_above_buttons(self):
        response = self.get_page(payment_links=PAY_LINKS)
        html = response.content.decode()
        intro = 'Register your child first, then pay with the option you chose.'
        self.assertIn(intro, html)
        # The intro must come before the first pay button.
        intro_pos = html.index(intro)
        first_url_pos = html.index(PAY_LINKS[0]['url'])
        self.assertLess(intro_pos, first_url_pos)


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class JoinThanksPaymentTests(SimpleTestCase):
    """Pay buttons on the join-thanks page follow programme and public flag."""

    def _get_thanks(self, programme='', public=True, payment_links=None):
        links = PAY_LINKS if payment_links is None else payment_links
        with mock.patch.dict(views.STEAM_EXPERIENCE, {'payment_links': links}):
            with self.settings(STEAM_EXPERIENCE_PUBLIC=public):
                return self.client.get(
                    THANKS_URL + ('?programme=%s' % programme if programme else '')
                )

    def test_holiday_and_public_shows_pay_buttons(self):
        response = self._get_thanks(programme='holiday', public=True)
        html = response.content.decode()
        self.assertIn('Ready to pay? Choose your option.', html)
        for link in PAY_LINKS:
            self.assertIn(link['url'], html)

    def test_holiday_not_public_hides_pay_buttons(self):
        response = self._get_thanks(programme='holiday', public=False)
        html = response.content.decode()
        self.assertNotIn('Ready to pay?', html)
        self.assertNotIn('kacyberpay', html.lower())

    def test_school_programme_hides_pay_buttons(self):
        response = self._get_thanks(programme='school', public=True)
        html = response.content.decode()
        self.assertNotIn('Ready to pay?', html)
        self.assertNotIn('kacyberpay', html.lower())

    def test_no_programme_hides_pay_buttons(self):
        response = self._get_thanks(programme='', public=True)
        html = response.content.decode()
        self.assertNotIn('Ready to pay?', html)
        self.assertNotIn('kacyberpay', html.lower())

    def test_empty_payment_links_hides_pay_section(self):
        response = self._get_thanks(programme='holiday', public=True, payment_links=[])
        html = response.content.decode()
        self.assertNotIn('Ready to pay?', html)

    def test_pay_buttons_open_in_new_tab_on_thanks_page(self):
        response = self._get_thanks(programme='holiday', public=True)
        html = response.content.decode()
        for link in PAY_LINKS:
            pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
            matches = re.findall(pattern, html)
            self.assertTrue(matches, 'No anchor for %s on thanks page' % link['url'])
            for anchor_open in matches:
                self.assertIn('target="_blank"', anchor_open)
                self.assertIn('rel="noopener noreferrer"', anchor_open)

    def test_pay_buttons_carry_pay_click_event_on_thanks_page(self):
        response = self._get_thanks(programme='holiday', public=True)
        html = response.content.decode()
        for link in PAY_LINKS:
            pattern = r'<a\b[^>]*href="%s"[^>]*>' % re.escape(link['url'])
            for anchor_open in re.findall(pattern, html):
                self.assertIn('data-umami-event="pay-click"', anchor_open)

    def test_thank_you_text_always_present(self):
        response = self._get_thanks(programme='weekend', public=True)
        self.assertContains(response, 'Thank you')
        self.assertContains(response, 'We have received your registration.')
