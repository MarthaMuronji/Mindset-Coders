from django.test import SimpleTestCase, override_settings

from .views import STEAM_EXPERIENCE


WHATSAPP_LINK = (
    'href="https://wa.me/256752064343" target="_blank" '
    'rel="noopener noreferrer"'
)
PHONE_LINK = 'href="tel:+256752064343"'


class ContactLinksTests(SimpleTestCase):
    def test_whatsapp_and_phone_links_render_on_each_page(self):
        with override_settings(STEAM_PAYMENTS_ENABLED=True):
            confirmation = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )
        responses = {
            'confirmation': confirmation,
            'STEAM Experience': self.client.get('/steam-experience/'),
            'Contact': self.client.get('/contact/'),
        }

        for name, response in responses.items():
            with self.subTest(page=name):
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, WHATSAPP_LINK)
                self.assertContains(response, PHONE_LINK)

    def test_cash_copy_only_appears_with_confirmation_payment(self):
        with override_settings(STEAM_PAYMENTS_ENABLED=True):
            paid = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )
        with override_settings(STEAM_PAYMENTS_ENABLED=False):
            plain = self.client.get(
                '/join/thanks/?programme=holiday&stage=build'
            )

        self.assertContains(
            paid, 'You can also pay in cash. Contact our team to arrange it.'
        )
        self.assertNotContains(
            plain, 'You can also pay in cash. Contact our team to arrange it.'
        )

    def test_payment_options_include_mobile_money_and_cash(self):
        self.assertEqual(
            STEAM_EXPERIENCE['payment_options'],
            'Pay online by Mobile Money. You can also pay in cash.',
        )
