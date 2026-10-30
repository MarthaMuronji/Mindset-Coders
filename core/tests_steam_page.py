import json
import re

from django.test import SimpleTestCase, override_settings


STEAM_URL = '/steam-experience/'
META_DESCRIPTION = (
    'Give your child a holiday filled with robotics, artificial intelligence, '
    'coding, creative arts and entrepreneurship. Join the Mindset STEAM '
    'Experience in Kampala.'
)


@override_settings(STEAM_EXPERIENCE_PUBLIC=False)
class SteamExperienceRedesignTests(SimpleTestCase):
    def setUp(self):
        self.response = self.client.get(STEAM_URL)
        self.html = self.response.content.decode()

    def test_single_h1_and_exact_hero_heading(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(len(re.findall(r'<h1\b', self.html)), 1)
        self.assertContains(
            self.response,
            "This holiday, let your child discover what they're capable of creating.",
        )

    def test_seo_title_and_description(self):
        self.assertContains(
            self.response,
            '<title>Mindset STEAM Experience 2026/2027 | Robotics, AI, Coding &amp; Creativity</title>',
        )
        self.assertContains(
            self.response,
            f'<meta name="description" content="{META_DESCRIPTION}">',
        )
        self.assertContains(
            self.response,
            f'<meta property="og:description" content="{META_DESCRIPTION}">',
        )

    def test_four_experience_cards_render(self):
        self.assertEqual(self.html.count('class="build-card steam-experience-card'), 4)
        for title in (
            'Robotics and Engineering',
            'AI and Coding',
            'Creative Arts and Design',
            'Entrepreneurship and Innovation',
        ):
            self.assertContains(self.response, title)

    def test_register_links_use_the_existing_join_routes(self):
        self.assertEqual(
            len(re.findall(r'href="/join/\?programme=holiday"', self.html)),
            3,
        )
        for stage in ('discover', 'build', 'innovate', 'full'):
            self.assertContains(
                self.response,
                f'href="/join/?programme=holiday&amp;stage={stage}"',
            )
        self.assertContains(
            self.response,
            'href="#programme-details"',
        )

    def test_whatsapp_link_and_event_render(self):
        self.assertContains(
            self.response,
            'href="https://wa.me/256752064343" target="_blank" rel="noopener noreferrer"',
        )
        self.assertContains(self.response, 'data-umami-event="whatsapp-click"')

    def test_faq_renders_answers_and_omits_empty_answers(self):
        self.assertContains(self.response, 'Learners aged 8 to 19 can take part.')
        self.assertContains(
            self.response,
            'Yes. You can register for Discover, Build or Innovate on its own.',
        )
        self.assertNotContains(
            self.response,
            'Does my child need prior coding or robotics experience?',
        )
        self.assertNotContains(
            self.response,
            'What happens if my child misses a session?',
        )

    def test_empty_gallery_age_groups_and_spaces_note_do_not_render(self):
        self.assertNotContains(self.response, 'steam-gallery')
        self.assertNotContains(self.response, 'steam-age-groups')
        self.assertNotContains(
            self.response,
            'Activities are differentiated by age and ability.',
        )
        self.assertNotContains(self.response, 'steam-spaces-note')

    def test_payment_addresses_do_not_appear_on_the_page_or_jsonld(self):
        self.assertNotContains(self.response, 'kacyberpay')


@override_settings(STEAM_EXPERIENCE_PUBLIC=True)
class PublicSteamEventJsonLdTests(SimpleTestCase):
    def test_event_jsonld_uses_registration_urls_and_dictionary_fees(self):
        response = self.client.get(STEAM_URL)
        html = response.content.decode()

        self.assertContains(response, 'type="application/ld+json"')
        self.assertNotIn('kacyberpay', html.lower())
        match = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            re.S,
        )
        self.assertIsNotNone(match)
        event = json.loads(match.group(1))

        self.assertEqual(event['@type'], 'Event')
        self.assertEqual(event['description'], META_DESCRIPTION)
        self.assertEqual(event['startDate'], '2026-11-16')
        self.assertEqual(event['endDate'], '2027-01-29')
        self.assertEqual(
            event['location'],
            {
                '@type': 'Place',
                'name': 'Amreena Mall, Level 3, room 304, Kyanja Ring Road, Kampala',
            },
        )
        self.assertEqual(
            event['organizer'],
            {'@type': 'Organization', 'name': 'Mindset Coders Uganda'},
        )
        self.assertEqual(len(event['offers']), 4)
        self.assertEqual(
            {
                offer['name']: (offer['price'], offer['priceCurrency'], offer['url'])
                for offer in event['offers']
            },
            {
                'Discover, 2 weeks': (
                    '300000',
                    'UGX',
                    'https://mindset-group.org/join/?programme=holiday',
                ),
                'Build, 3 weeks': (
                    '400000',
                    'UGX',
                    'https://mindset-group.org/join/?programme=holiday',
                ),
                'Innovate, 4 weeks': (
                    '500000',
                    'UGX',
                    'https://mindset-group.org/join/?programme=holiday',
                ),
                'Full journey, paid upfront': (
                    '1100000',
                    'UGX',
                    'https://mindset-group.org/join/?programme=holiday',
                ),
            },
        )
