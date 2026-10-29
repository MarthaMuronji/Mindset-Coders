"""The STEAM Experience payment link.

The page is rendered from the STEAM_EXPERIENCE dictionary alone, so every
test here uses SimpleTestCase and needs no database.
"""

import re
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import views

PAYMENT_LINK = 'https://kacyberpay.com/pay/f47mjrdxje'

# The hero, the contact section and the sticky bar at the bottom of the page.
REGISTER_BUTTONS = 3


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
class RegisterPaymentLinkTests(SteamPageTestCase):
    """Each Register button opens the payment link, and nothing else."""

    def test_page_still_renders_without_a_database(self):
        response = self.get_page(registration_url=PAYMENT_LINK)
        self.assertEqual(response.status_code, 200)

    def test_every_register_button_points_at_the_payment_link(self):
        response = self.get_page(registration_url=PAYMENT_LINK)
        html = response.content.decode()
        anchors = register_anchors(html, PAYMENT_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        # No Register button falls back to the contact page any more.
        self.assertEqual(register_anchors(html, '/contact/'), [])

    def test_every_register_button_opens_in_a_new_tab(self):
        response = self.get_page(registration_url=PAYMENT_LINK)
        html = response.content.decode()
        anchors = register_anchors(html, PAYMENT_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        for anchor in anchors:
            self.assertIn('target="_blank"', anchor)
            self.assertIn('rel="noopener noreferrer"', anchor)

    def test_every_register_button_sends_the_payment_click_event(self):
        response = self.get_page(registration_url=PAYMENT_LINK)
        html = response.content.decode()
        anchors = register_anchors(html, PAYMENT_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        for anchor in anchors:
            self.assertIn('data-umami-event="register-payment-click"', anchor)
            self.assertIn('data-umami-event-from="steam-experience"', anchor)

    def test_no_sdk_script_is_loaded(self):
        # The plain link is all the page uses, so no script may mention the
        # payment provider at all.
        response = self.get_page(registration_url=PAYMENT_LINK)
        html = response.content.decode()
        self.assertIsNone(re.search(r'<script[^>]*kacyberpay', html, re.I))
        # Every mention of the provider sits inside a link href.
        hrefs = re.findall(r'href="[^"]*kacyberpay[^"]*"', html, re.I)
        self.assertEqual(len(hrefs), REGISTER_BUTTONS)
        self.assertEqual(html.lower().count('kacyberpay'), len(hrefs))

    def test_merchant_pay_does_not_appear(self):
        response = self.get_page(registration_url=PAYMENT_LINK)
        html = response.content.decode()
        self.assertNotContains(response, 'Merchant Pay')
        self.assertIsNone(re.search(r'merchant\s+pay', html, re.I))
        # The rest of the sentence is unchanged.
        self.assertContains(response, 'Pay online by Mobile Money or by card.')

    def test_register_button_keeps_the_contact_fallback_when_no_link(self):
        response = self.get_page(registration_url=None)
        html = response.content.decode()
        anchors = register_anchors(html, '/contact/')
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        for anchor in anchors:
            self.assertNotIn('target="_blank"', anchor)
            self.assertIn('data-umami-event="steam-register-interest"', anchor)


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
