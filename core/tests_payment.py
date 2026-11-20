"""Tests for registration and payment guidance on the STEAM Experience page."""

import re
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import views

JOIN_LINK = '/join/?programme=holiday'
REGISTER_BUTTONS = 3


def register_anchors(html, href):
    """Every Register link on the page that points at href."""
    pattern = r'<a\b[^>]*href="%s"[^>]*>.*?</a>' % re.escape(href)
    return [
        anchor for anchor in re.findall(pattern, html, re.S)
        if 'register your child' in anchor.lower()
    ]


class SteamPageTestCase(SimpleTestCase):
    """Renders the STEAM Experience page with optional dictionary overrides."""

    def get_page(self, **overrides):
        with mock.patch.dict(views.STEAM_EXPERIENCE, overrides):
            return self.client.get('/steam-experience/')


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class RegisterLinkTests(SteamPageTestCase):
    def test_page_still_renders_without_a_database(self):
        response = self.get_page()
        self.assertEqual(response.status_code, 200)

    def test_every_register_button_points_at_the_join_route(self):
        response = self.get_page()
        anchors = register_anchors(response.content.decode(), JOIN_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)

    def test_registration_guidance_has_no_pay_button(self):
        response = self.get_page()
        self.assertContains(
            response,
            'Choose how to pay when you register: Mobile Money or cash at the venue.',
        )
        self.assertContains(
            response,
            'Register your child first. You will see your fee and payment options on the next page.',
        )
        self.assertNotContains(response, 'data-umami-event="pay-click"')

    def test_every_register_button_sends_the_register_click_event(self):
        response = self.get_page()
        anchors = register_anchors(response.content.decode(), JOIN_LINK)
        self.assertEqual(len(anchors), REGISTER_BUTTONS)
        for anchor in anchors:
            self.assertIn('data-umami-event="register-click"', anchor)
            self.assertIn('data-umami-event-from="steam-experience"', anchor)


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class PaymentNoteTests(SteamPageTestCase):
    NOTE = 'A short note for the test'

    def test_empty_note_renders_nothing_extra(self):
        response = self.get_page(payment_note=None)
        self.assertNotIn('steam-payment-note', response.content.decode())

    def test_filled_note_shows_one_line_with_registration_details(self):
        response = self.get_page(payment_note=self.NOTE)
        html = response.content.decode()
        self.assertContains(response, self.NOTE)
        self.assertEqual(html.count('steam-payment-note'), 1)
