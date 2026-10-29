from django.test import SimpleTestCase, override_settings

from .sitemaps import StaticViewSitemap


SOCIAL_LINKS = {
    'Facebook': 'https://www.facebook.com/mindsetcoders/',
    'Instagram': 'https://www.instagram.com/mindsetcoders/',
    'X': 'https://x.com/mindsetcoder',
    'LinkedIn': 'https://ug.linkedin.com/company/mindsetcoders',
}


class SteamExperienceSiteTests(SimpleTestCase):
    @override_settings(STEAM_EXPERIENCE_PUBLIC=False, STEAM_PAYMENTS_ENABLED=False)
    def test_dates_and_break_appear(self):
        response = self.client.get('/steam-experience/')

        self.assertContains(response, 'Discover: 16 to 27 November 2026')
        self.assertContains(response, 'Build: 30 November to 18 December 2026')
        self.assertContains(response, 'Christmas break: 21 December 2026 to 2 January 2027')
        self.assertContains(response, 'Innovate: 4 to 29 January 2027')
        self.assertContains(response, 'Classes resume on Monday, 4 January 2027.')
        self.assertContains(response, 'The programme follows the Discover, Build, Innovate pathway across nine teaching weeks.')

    @override_settings(STEAM_EXPERIENCE_PUBLIC=False, STEAM_PAYMENTS_ENABLED=False)
    def test_payment_links_are_not_rendered_and_sibling_note_appears_once(self):
        response = self.client.get('/steam-experience/')

        for payment_url in (
            'https://kacyberpay.com/pay/f47mjrdxje',
            'https://kacyberpay.com/pay/ys7azaf25a',
            'https://kacyberpay.com/pay/gjuffbu4je',
            'https://kacyberpay.com/pay/hc6sn7yqxq',
        ):
            self.assertNotContains(response, payment_url)
        for payment_label in (
            'Discover, 2 weeks - UGX 300,000',
            'Build, 3 weeks - UGX 400,000',
            'Innovate, 4 weeks - UGX 500,000',
            'Full journey, paid upfront - UGX 1,100,000',
        ):
            self.assertNotContains(response, payment_label)
        self.assertNotContains(response, 'Register your child first, then pay with the option you chose.')
        self.assertContains(
            response,
            'Registering more than one child? Contact our team to arrange your 10% sibling discount before making payment.',
            count=1,
        )
        self.assertContains(response, 'Register your child first. Our team will tell you how to pay.')
        self.assertContains(response, 'Read the refund and cancellation policy')

    @override_settings(STEAM_EXPERIENCE_PUBLIC=False, STEAM_PAYMENTS_ENABLED=True)
    def test_enabled_payment_copy_is_shown(self):
        response = self.client.get('/steam-experience/')

        self.assertContains(response, 'Register your child first. You will see your fee and the payment button on the next page.')


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class RefundPolicySiteTests(SimpleTestCase):
    def test_page_renders_noindex_without_umami(self):
        response = self.client.get('/refund-policy/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Refund and cancellation policy</h1>')
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertNotContains(response, 'cloud.umami.is/script.js')
        for policy in (
            'Registration is confirmed once payment has been received.',
            'Cancellations requested at least seven days before the registered stage begins may qualify for a refund, subject to any reasonable administrative deductions disclosed before payment.',
            'Cancellations requested less than seven days before a stage begins are generally non-refundable, except where an exception is approved.',
            'Once a stage has started, fees are generally non-refundable.',
            'If Mindset Coders cancels a programme, parents will be offered a full refund or the option to transfer their payment to another programme.',
            'Exceptional circumstances will be considered individually.',
        ):
            self.assertContains(response, policy)

    def test_page_is_not_in_the_sitemap(self):
        self.assertNotIn('refund_policy', StaticViewSitemap().items())


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class PublicRefundPolicySiteTests(SimpleTestCase):
    def test_page_is_in_the_sitemap_when_steam_experience_is_public(self):
        self.assertIn('refund_policy', StaticViewSitemap().items())


class PrivacySiteTests(SimpleTestCase):
    def test_safeguarding_and_data_protection_copy_appears(self):
        response = self.client.get('/privacy/')

        self.assertContains(response, 'Child Safeguarding')
        self.assertContains(
            response,
            'Mindset Coders is committed to providing a safe, inclusive and respectful learning environment where every child can participate, explore, create and learn. We take child safeguarding seriously and work to protect children from abuse, exploitation, discrimination and harm throughout our programmes and activities.',
        )
        self.assertContains(response, 'Privacy and Data Protection')
        self.assertContains(
            response,
            "Mindset Coders respects the privacy of learners and their families. We collect personal information for legitimate programme, learning, communication and administrative purposes and take appropriate measures to protect it from unauthorised access, use or disclosure. Access is restricted to authorised personnel who need the information for their work. Children's photographs, videos and identifiable stories will only be used with appropriate consent. We do not sell children's personal information.",
        )


class HeaderAndSocialSiteTests(SimpleTestCase):
    def test_header_has_no_login_and_keeps_m_pass(self):
        response = self.client.get('/')

        self.assertNotContains(response, '>Login</a>')
        self.assertContains(
            response,
            '<a href="https://mpass.mindsetlearn.org/auth" target="_blank" rel="noopener noreferrer" data-umami-event="go-mpass" data-umami-event-from="home">M-Pass</a>',
        )

    def test_social_links_render_in_footer_and_contact(self):
        home = self.client.get('/')
        contact = self.client.get('/contact/')

        for network, url in SOCIAL_LINKS.items():
            link = (
                f'href="{url}" target="_blank" rel="noopener noreferrer" '
                f'aria-label="{network}" data-umami-event="social-click"'
            )
            network_name = network.lower()
            self.assertContains(home, link, count=1)
            self.assertContains(home, f'data-umami-event-network="{network_name}"')
            self.assertContains(contact, link, count=2)
