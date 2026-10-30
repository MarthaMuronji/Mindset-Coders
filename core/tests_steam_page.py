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

    def test_faq_renders_confirmed_answers_and_omits_empty_answers(self):
        self.assertContains(
            self.response,
            'Learners aged 8 to 19 can take part, in three groups: Juniors (8 to 11 years), Explorers (12 to 14 years) and Young Innovators (15 to 19 years). Activities are differentiated by age and ability.',
        )
        self.assertContains(
            self.response,
            'Every learner begins with the Discover stage, then continues to Build and Innovate. You can register stage by stage, or choose the complete journey.',
        )
        self.assertContains(
            self.response,
            'No prior coding, robotics or AI experience is required. However, every learner must begin with the Discover stage before progressing to Build and Innovate. This ensures everyone develops the necessary foundation.',
        )
        self.assertContains(
            self.response,
            'Does my child need prior coding or robotics experience?',
        )
        self.assertContains(
            self.response,
            'Kits are used during the Build stage, and learners take a kit home in the Innovate stage. No additional purchases are required. The programme fee covers the learning experience and required materials.',
        )
        self.assertNotContains(
            self.response,
            'What happens if my child misses a session?',
        )

    def test_empty_gallery_does_not_render(self):
        self.assertNotContains(self.response, 'steam-gallery')

    def test_venue_is_consistent_across_steam_contact_and_home(self):
        venue = 'Amreena Mall, Level 3, Room 304, Kyanja Ring Road'
        self.assertContains(self.response, venue)
        self.assertContains(self.client.get('/contact/'), venue)
        with override_settings(STEAM_EXPERIENCE_PUBLIC=True):
            home = self.client.get('/')
        self.assertContains(home, venue)

    def test_confirmed_age_groups_spaces_and_purchase_note_render(self):
        for group in (
            'Juniors: 8 to 11 years',
            'Explorers: 12 to 14 years',
            'Young Innovators: 15 to 19 years',
        ):
            self.assertContains(self.response, group)
        self.assertContains(
            self.response,
            'Activities are differentiated by age and ability.',
        )
        self.assertContains(self.response, 'Spaces are limited.')
        self.assertContains(
            self.response,
            'No additional purchases are required. The programme fee covers the learning experience and required materials.',
        )

    def test_mpass_link_is_absent_from_page_body(self):
        body = self.html.split('<main>', 1)[1].split('</main>', 1)[0]
        self.assertNotIn('mpass.mindsetlearn.org', body)
        self.assertContains(self.response, 'Every learner gets an M-Pass')

    def test_stage_cards_and_join_flow_explain_discover_first(self):
        for stage in ('Build', 'Innovate'):
            card_start = self.html.index(f'<h3>{stage}</h3>')
            card_end = self.html.index('</article>', card_start)
            card = self.html[card_start:card_end]
            button_position = card.index(f'Register for {stage}')
            note_position = card.index(
                'Learners must complete the Discover stage first.'
            )
            self.assertLess(button_position, note_position)

        join_response = self.client.get('/join/')
        self.assertContains(
            join_response,
            'Every learner begins with Discover. Choose Build or Innovate only if your child has already completed Discover.',
        )

    def test_build_and_innovate_confirmation_pages_explain_discover_first(self):
        with override_settings(STEAM_PAYMENTS_ENABLED=True):
            for stage in ('build', 'innovate'):
                with self.subTest(stage=stage):
                    response = self.client.get(
                        f'/join/thanks/?programme=holiday&stage={stage}'
                    )
                    html = response.content.decode()
                    fee_position = html.index('class="join-thanks-fee"')
                    note_position = html.index(
                        'Learners must complete the Discover stage first.'
                    )
                    self.assertLess(fee_position, note_position)

    def test_complete_journey_is_prominent_and_repeated_in_final_cta(self):
        self.assertContains(self.response, 'UGX 1,100,000')
        self.assertContains(self.response, 'when paid upfront')
        self.assertContains(self.response, 'Save UGX 100,000')
        self.assertContains(self.response, 'Covers Discover, Build and Innovate.')
        self.assertContains(
            self.response,
            'href="/join/?programme=holiday&amp;stage=full"',
            count=2,
        )
        self.assertContains(self.response, 'Register for the complete journey')

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
                'name': 'Amreena Mall',
                'address': {
                    '@type': 'PostalAddress',
                    'streetAddress': 'Amreena Mall, Level 3, Room 304, Kyanja Ring Road',
                    'addressLocality': 'Kampala',
                    'addressCountry': 'UG',
                },
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
